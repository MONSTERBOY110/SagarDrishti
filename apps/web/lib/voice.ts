/** Voice for Samudra Sahayak (PRD F10).
 *
 * THE BROWSER NEVER TALKS TO BHASHINI. Every speech call goes to our own agent
 * service, which holds the key and makes the outbound request
 * (services/agent/app/voice.py). The page therefore still talks only to our
 * own origin set, and the off-origin guard in e2e/demo-path.spec.ts keeps
 * meaning what it says.
 *
 * OFFLINE IS A STATED STATE, NOT A BROKEN BUTTON. When the agent reports that
 * voice is unavailable, the microphone says why in words, and English answers
 * can still be read aloud by the operating system's own speech synthesiser,
 * which needs no network at all.
 */

const AGENT_BASE = process.env.NEXT_PUBLIC_AGENT_BASE ?? "http://127.0.0.1:8010";

export type VoiceLang = "en" | "hi" | "te" | "ta";

export interface VoiceStatus {
  available: boolean;
  reason: string;
  message: string;
  languages: Record<VoiceLang, string>;
}

export interface Heard {
  language: VoiceLang;
  transcript: string;
  english: string;
  machine_translation: boolean;
}

export interface Spoken {
  language: VoiceLang;
  english: string;
  text: string;
  machine_translation: boolean;
  audio: string;
  audio_format: string;
}

/** The rate the agent tells Bhashini the audio is at. Resampled here, so it is
 *  a fact rather than a hope about what the microphone produced. */
const ASR_RATE = 16000;

async function post<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${AGENT_BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal: AbortSignal.timeout(30000),
  });
  if (!r.ok) {
    let message = `${r.status} ${r.statusText}`;
    try {
      const d = (await r.json()).detail;
      message = typeof d === "string" ? d : (d?.message ?? message);
    } catch {
      /* a non-JSON error body is still an error */
    }
    throw new Error(message);
  }
  return r.json() as Promise<T>;
}

export const voice = {
  async status(): Promise<VoiceStatus> {
    const r = await fetch(`${AGENT_BASE}/voice/status`, { signal: AbortSignal.timeout(8000) });
    if (!r.ok) throw new Error(`voice ${r.status}`);
    return r.json() as Promise<VoiceStatus>;
  },
  asr: (audio: string, language: VoiceLang) => post<Heard>("/voice/asr", { audio, language }),
  speak: (text: string, language: VoiceLang) => post<Spoken>("/voice/speak", { text, language }),
};

/** Can this browser read English aloud with no network? */
export function canSpeakLocally(): boolean {
  return typeof window !== "undefined" && "speechSynthesis" in window;
}

/** Read an English answer aloud with the operating system's own voice. */
export function speakLocally(text: string): void {
  if (!canSpeakLocally()) return;
  window.speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = "en-IN";
  // An Indian English voice when the machine has one (Windows ships Heera and
  // Ravi), chosen by name rather than left to the browser, so the demo video
  // and the live app speak with the same voice.
  const voices = window.speechSynthesis.getVoices();
  const v =
    voices.find((x) => x.lang === "en-IN" && /Heera/i.test(x.name)) ??
    voices.find((x) => x.lang === "en-IN");
  if (v) u.voice = v;
  window.speechSynthesis.speak(u);
}

export function stopSpeaking(): void {
  if (canSpeakLocally()) window.speechSynthesis.cancel();
}

/** Play base64 WAV from the agent. Returns once playback has started. */
export async function playWav(b64: string): Promise<HTMLAudioElement> {
  const a = new Audio(`data:audio/wav;base64,${b64}`);
  await a.play();
  return a;
}

/** Push-to-talk: start recording, and get back a function that stops it and
 *  resolves to 16 kHz mono WAV as base64. */
export async function startRecording(): Promise<() => Promise<string>> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
  const rec = new MediaRecorder(stream);
  const chunks: Blob[] = [];
  rec.ondataavailable = (e) => {
    if (e.data.size) chunks.push(e.data);
  };
  rec.start();
  return () =>
    new Promise<string>((resolve, reject) => {
      rec.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        try {
          const blob = new Blob(chunks, { type: rec.mimeType });
          resolve(await toWav16k(await blob.arrayBuffer()));
        } catch (e) {
          reject(e);
        }
      };
      rec.stop();
    });
}

/** Decode whatever the recorder produced, resample to mono 16 kHz, and encode
 *  as 16-bit PCM WAV. Done here so the server needs no audio codec. */
async function toWav16k(buf: ArrayBuffer): Promise<string> {
  const ctx = new AudioContext();
  const decoded = await ctx.decodeAudioData(buf);
  await ctx.close();
  const frames = Math.ceil(decoded.duration * ASR_RATE);
  const off = new OfflineAudioContext(1, frames, ASR_RATE);
  const src = off.createBufferSource();
  src.buffer = decoded;
  src.connect(off.destination);
  src.start();
  const pcm = (await off.startRendering()).getChannelData(0);

  const out = new DataView(new ArrayBuffer(44 + pcm.length * 2));
  const str = (o: number, s: string) => [...s].forEach((c, i) => out.setUint8(o + i, c.charCodeAt(0)));
  str(0, "RIFF");
  out.setUint32(4, 36 + pcm.length * 2, true);
  str(8, "WAVE");
  str(12, "fmt ");
  out.setUint32(16, 16, true);
  out.setUint16(20, 1, true); // PCM
  out.setUint16(22, 1, true); // mono
  out.setUint32(24, ASR_RATE, true);
  out.setUint32(28, ASR_RATE * 2, true);
  out.setUint16(32, 2, true);
  out.setUint16(34, 16, true);
  str(36, "data");
  out.setUint32(40, pcm.length * 2, true);
  for (let i = 0; i < pcm.length; i++) {
    const v = Math.max(-1, Math.min(1, pcm[i]));
    out.setInt16(44 + i * 2, v < 0 ? v * 0x8000 : v * 0x7fff, true);
  }

  const bytes = new Uint8Array(out.buffer);
  let bin = "";
  for (let i = 0; i < bytes.length; i += 0x8000) {
    bin += String.fromCharCode(...bytes.subarray(i, i + 0x8000));
  }
  return btoa(bin);
}
