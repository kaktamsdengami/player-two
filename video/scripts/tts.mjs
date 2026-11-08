// Voice-over for the demo video: ElevenLabs /with-timestamps -> public/vo/<id>.mp3 (loudnorm -16 LUFS)
// + src/data/vo_<id>.json (character timings for the captions).
// Usage (from video/): node scripts/tts.mjs p1 p7 ...   (ids from LINES; no ids = all)
import { execFileSync } from 'node:child_process'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'

const VOICE = 'EXAVITQu4vr4xnSDxMaL' // Sarah, same as s1..s8
const SETTINGS = { stability: 0.45, similarity_boost: 0.8, style: 0.15, use_speaker_boost: true }

export const LINES = {
  p1: 'Doom is over thirty years old. This sky bug has been in its code since 1993, and it is still in Chocolate Doom and Crispy Doom today. Tonight, an AI tester found it, and Devin fixed it.',
  p7: 'Under three minutes to find it. About seven minutes from "fix it" to proof. One agent, one night, and a bug that sat in the code for thirty-three years.',
  v1: 'Now imagine what it could do with real investment: more time, more compute, more tokens.',
  v2: 'Point it at worlds the size of GTA 6. At Spider-Man, at Wolverine, at the next James Bond.',
  v3: 'Today, games like these need large QA teams and months of manual testing. And bugs still ship.',
  v4: 'PLAYER TWO is one program, connected to your game and to your code. It plays, finds the bug, proves it, and gets the fix written.',
  // tight cut (Tight.tsx)
  st: 'And we did not make it easy. Monsters shot at it the whole way. Its health fell from 999 to 441, and it still reached the power-up.',
  p3: 'It grabs invulnerability. The whole screen should invert, but the sky stays red. So H files a bug report: a title, the steps it took, and what it saw.',
  p5a: 'The developer answers out loud: yes, fix it.',
  p6b: 'Before the fix, and after.',
  // real-footage cut (Real.tsx): screen recording of the 02:26 UTC run
  r1: 'This is PLAYER TWO, recorded live on our laptop. On the left, Chocolate Doom. On the right, our dashboard. H, a computer-use agent, plays from the pixels, with a keyboard. The game waits while it thinks, so we sped this up sixteen times. Monsters shoot at it the whole way. Its health drops all the way to four hundred and forty-one.',
  r2: 'It reaches the green sphere. Invulnerability turns the world white, but the sky stays red. H reports the bug, with steps to reproduce.',
  r3: "Our verifier replays H's exact inputs, and reads a hidden engine log that H never saw. The bug is real.",
  r4: 'The developer answers: yes, fix it.',
  r5: "Our backend sends the finding to Devin, through its API. Two minutes later, Devin's pull request is up: a fix in the 1993 renderer. It is merged, and CI rebuilds the game.",
  r6: "On the new build, our proof script replays the same scenario. Now the sky inverts too. Fixed, six and a half minutes after 'fix it'.",
  r8: 'Devin built this product, and works inside it. Today it tests Doom. Next, the games that studios spend months testing. PLAYER TWO. The link is on screen.',
  k7: 'The same eyes power Pixel, a game buddy. H sees the screen, Gladia hears you, ElevenLabs talks back.',
}

const env = Object.fromEntries(
  readFileSync('../.env', 'utf8').split(/\r?\n/).filter((l) => /^[A-Z_]+=/.test(l)).map((l) => {
    const i = l.indexOf('='); return [l.slice(0, i), l.slice(i + 1).trim().replace(/^["']|["']$/g, '')]
  }),
)
const key = process.env.ELEVENLABS_API_KEY ?? env.ELEVENLABS_API_KEY
if (!key) throw new Error('ELEVENLABS_API_KEY missing')

mkdirSync('public/vo', { recursive: true })
for (const id of process.argv.slice(2).length ? process.argv.slice(2) : Object.keys(LINES)) {
  const text = LINES[id]
  const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${VOICE}/with-timestamps?output_format=mp3_44100_128`, {
    method: 'POST',
    headers: { 'xi-api-key': key, 'content-type': 'application/json' },
    body: JSON.stringify({ text, model_id: 'eleven_multilingual_v2', voice_settings: SETTINGS }),
  })
  if (!r.ok) throw new Error(`${id}: ${r.status} ${await r.text()}`)
  const j = await r.json()
  writeFileSync(`public/vo/${id}.raw.mp3`, Buffer.from(j.audio_base64, 'base64'))
  execFileSync('ffmpeg', ['-v', 'error', '-y', '-i', `public/vo/${id}.raw.mp3`, '-af', 'loudnorm=I=-16:TP=-1.5:LRA=11', '-ar', '44100', '-b:a', '192k', `public/vo/${id}.mp3`])
  const a = j.alignment
  const vo = { text, chars: a.characters, start: a.character_start_times_seconds, end: a.character_end_times_seconds }
  writeFileSync(`src/data/vo_${id}.json`, JSON.stringify(vo))
  console.log(id, vo.end[vo.end.length - 1].toFixed(2), 's')
}
