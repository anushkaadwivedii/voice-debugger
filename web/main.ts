import { Room, RoomEvent, Track, ParticipantKind, createLocalAudioTrack, type Participant, type LocalAudioTrack } from 'livekit-client';
import './style.css';

const element = <T extends HTMLElement = HTMLElement>(id: string) => document.getElementById(id) as T;
const start = element<HTMLButtonElement>('start');
const mute = element<HTMLButtonElement>('mute');
const end = element<HTMLButtonElement>('end');
const playAudio = element<HTMLButtonElement>('play-audio');
const errorBox = element('error');
const transcript = element('transcript');
let room: Room | undefined;
let microphone: LocalAudioTrack | undefined;
let active = false;
let starting = false;
let muted = false;
let attempt = 0;
let ticker: ReturnType<typeof setInterval> | undefined;
let agentTimeout: ReturnType<typeof setTimeout> | undefined;
let limitSeconds = 300;
let configured = false;
const segments = new Map<string, HTMLElement>();

function showError(message: string) {
  errorBox.textContent = message;
  errorBox.hidden = false;
}

function setState(label: string, mode = 'idle') {
  element('state').textContent = label;
  element('orb').dataset.state = mode;
  element('state-badge').dataset.state = mode;
}

function renderControls() {
  start.hidden = active;
  start.disabled = starting || !configured;
  start.querySelector('span')!.textContent = starting ? 'Connecting…' : 'Start conversation';
  mute.hidden = !active;
  end.hidden = !active && !starting;
  mute.textContent = muted ? 'Unmute microphone' : 'Mute microphone';
  mute.setAttribute('aria-pressed', String(muted));
}

async function checkSetup() {
  const button = element<HTMLButtonElement>('recheck');
  button.disabled = true;
  try {
    const response = await fetch('/api/config', { cache: 'no-store' });
    if (!response.ok) throw new Error('Could not check the local setup.');
    const config: { configured: boolean; missing: string[]; sessionLimitSeconds: number } = await response.json();
    configured = config.configured;
    limitSeconds = config.sessionLimitSeconds;
    element('setup').hidden = configured;
    element('setup-description').textContent = 'Your accounts are ready to connect. Add their credentials to the local .env file to finish setup.';
    element('missing-fields').textContent = `Still needed: ${config.missing.join(', ')}`;
    if (!active && !starting) setState(configured ? 'Ready when you are' : 'Account setup needed');
    if (configured) errorBox.hidden = true;
  } catch {
    configured = false;
    setState('Server unavailable', 'error');
    showError('The local server is unavailable. Start it with python3 run.py, then check again.');
    element('setup').hidden = false;
    element('setup-description').textContent = 'Start the local server to check your account configuration.';
  } finally {
    button.disabled = false;
    renderControls();
  }
}

function updateAgentState(participant: Participant) {
  if (!active || participant.kind !== ParticipantKind.AGENT) return;
  const state = participant.attributes['lk.agent.state'];
  if (state && state !== 'initializing') {
    clearTimeout(agentTimeout);
    agentTimeout = undefined;
  }
  const labels: Record<string, string> = { initializing: 'Getting ready…', listening: 'Listening', thinking: 'Thinking it through', speaking: 'Speaking' };
  setState(muted ? 'Your microphone is muted' : labels[state] || 'Waiting for your assistant…', muted ? 'idle' : state || 'connecting');
}

function appendTranscript(key: string, speaker: string, text: string) {
  if (!text.trim()) return;
  element('transcript-empty').hidden = true;
  let row = segments.get(key);
  if (!row) {
    row = document.createElement('div');
    row.className = `transcript-row ${speaker === 'You' ? 'from-user' : 'from-agent'}`;
    const name = document.createElement('span');
    name.className = 'speaker';
    name.textContent = speaker;
    const content = document.createElement('p');
    row.append(name, content);
    transcript.append(row);
    segments.set(key, row);
  }
  row.querySelector('p')!.textContent = text;
  transcript.scrollTop = transcript.scrollHeight;
}

async function stopSession(message = 'Session ended') {
  attempt += 1;
  active = false;
  starting = false;
  clearInterval(ticker);
  clearTimeout(agentTimeout);
  const oldRoom = room;
  room = undefined;
  microphone?.stop();
  microphone = undefined;
  muted = false;
  playAudio.hidden = true;
  element('remote-audio').replaceChildren();
  if (oldRoom) {
    oldRoom.removeAllListeners();
    await oldRoom.disconnect();
  }
  setState(message);
  renderControls();
}

async function startSession() {
  if (starting || active || !configured) return;
  starting = true;
  const currentAttempt = ++attempt;
  errorBox.hidden = true;
  setState('Preparing your microphone…', 'connecting');
  renderControls();
  let localRoom: Room | undefined;
  let localMic: LocalAudioTrack | undefined;
  try {
    // Capture permission before making a cloud connection or starting model usage.
    localMic = await createLocalAudioTrack({ echoCancellation: true, noiseSuppression: true, autoGainControl: true });
    if (attempt !== currentAttempt) { localMic.stop(); return; }
    microphone = localMic;
    const response = await fetch('/api/session', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
      signal: AbortSignal.timeout(10000),
    });
    if (!response.ok) throw new Error(response.status === 503 ? 'Save your credentials in .env, restart the app, and check setup again.' : 'Could not create a session. Check the local server and try again.');
    const connection: { url: string; token: string; sessionLimitSeconds: number } = await response.json();
    if (attempt !== currentAttempt) { localMic.stop(); return; }
    localRoom = new Room({ adaptiveStream: true, dynacast: true });
    const sessionRoom = localRoom;
    room = sessionRoom;
    segments.clear();
    transcript.querySelectorAll('.transcript-row').forEach((row) => row.remove());
    element('transcript-empty').hidden = false;

    sessionRoom.on(RoomEvent.TrackSubscribed, (track) => {
      if (track.kind === Track.Kind.Audio) {
        const audio = track.attach();
        element('remote-audio').append(audio);
      }
    });
    sessionRoom.on(RoomEvent.TrackUnsubscribed, (track) => track.detach().forEach((audio) => audio.remove()));
    sessionRoom.on(RoomEvent.ParticipantAttributesChanged, (_attributes, participant) => updateAgentState(participant));
    sessionRoom.on(RoomEvent.ParticipantConnected, (participant) => updateAgentState(participant));
    sessionRoom.on(RoomEvent.AudioPlaybackStatusChanged, () => { playAudio.hidden = sessionRoom.canPlaybackAudio; });
    sessionRoom.on(RoomEvent.Reconnecting, () => setState('Reconnecting…', 'connecting'));
    sessionRoom.on(RoomEvent.Reconnected, () => {
      setState('Connected again');
      sessionRoom.remoteParticipants.forEach(updateAgentState);
    });
    sessionRoom.on(RoomEvent.Disconnected, () => {
      if (room === sessionRoom) void stopSession('Session ended');
    });
    sessionRoom.registerTextStreamHandler('lk.transcription', async (reader, participant) => {
      try {
        const attributes = reader.info.attributes ?? {};
        if (attributes['lk.transcription_final'] === 'false') return;
        const text = await reader.readAll();
        if (attempt !== currentAttempt) return;
        const key = `${participant.identity}:${attributes['lk.segment_id'] || reader.info.id}`;
        appendTranscript(key, participant.identity === sessionRoom.localParticipant.identity ? 'You' : 'Voice Debugger', text);
      } catch {
        // A disconnected text stream should not end an otherwise healthy voice call.
      }
    });

    setState('Connecting…', 'connecting');
    await sessionRoom.connect(connection.url, connection.token);
    if (attempt !== currentAttempt) { await sessionRoom.disconnect(); localMic.stop(); return; }
    await sessionRoom.localParticipant.publishTrack(localMic);
    if (attempt !== currentAttempt) { await sessionRoom.disconnect(); localMic.stop(); return; }
    active = true;
    starting = false;
    setState('Waiting for your assistant…', 'connecting');
    renderControls();
    agentTimeout = setTimeout(() => {
      if (room !== sessionRoom) return;
      void stopSession('Assistant unavailable');
      showError('The assistant did not become ready. Check the Python agent terminal, your API keys, and your free-tier model quota, then try again.');
    }, 30000);
    sessionRoom.remoteParticipants.forEach(updateAgentState);
    try { await sessionRoom.startAudio(); } catch { playAudio.hidden = false; }
    if (attempt !== currentAttempt || room !== sessionRoom) return;
    if (!sessionRoom.canPlaybackAudio) playAudio.hidden = false;
    const deadline = Date.now() + connection.sessionLimitSeconds * 1000;
    ticker = setInterval(() => {
      const remaining = Math.max(0, Math.ceil((deadline - Date.now()) / 1000));
      element('timer').textContent = `${Math.floor(remaining / 60).toString().padStart(2, '0')}:${(remaining % 60).toString().padStart(2, '0')}`;
      if (remaining === 0) void stopSession('Five-minute session complete');
    }, 250);
  } catch (error) {
    localMic?.stop();
    if (attempt !== currentAttempt) { await localRoom?.disconnect(); return; }
    await stopSession('Let’s try that again');
    const name = error instanceof Error ? error.name : '';
    const message = name === 'NotAllowedError' ? 'Microphone access was not allowed. Enable it for this local page, then try again.'
      : name === 'NotFoundError' ? 'No microphone was found. Connect one and try again.'
      : error instanceof Error && error.message.startsWith('Save your credentials') ? error.message
      : 'Could not start the conversation. Check the microphone, internet connection, account credentials, and agent terminal, then try again.';
    showError(message);
  }
}

start.addEventListener('click', () => void startSession());
end.addEventListener('click', () => void stopSession());
element('recheck').addEventListener('click', () => void checkSetup());
mute.addEventListener('click', async () => {
  if (!microphone || !active) return;
  mute.disabled = true;
  try {
    if (muted) await microphone.unmute(); else await microphone.mute();
    muted = !muted;
    setState(muted ? 'Your microphone is muted' : 'Listening', muted ? 'idle' : 'listening');
    renderControls();
  } catch { showError('Could not change the microphone. End the session and try again.'); }
  finally { mute.disabled = false; }
});
playAudio.addEventListener('click', async () => {
  try { await room?.startAudio(); playAudio.hidden = room?.canPlaybackAudio ?? true; }
  catch { showError('Speaker playback is blocked. Check this browser’s audio settings.'); }
});
window.addEventListener('pagehide', () => { microphone?.stop(); void room?.disconnect(); });
element('timer').textContent = `${Math.floor(limitSeconds / 60).toString().padStart(2, '0')}:00`;
void checkSetup();
