// Voice-over for the demo video: ElevenLabs /with-timestamps -> public/vo/<id>.mp3 (loudnorm -16 LUFS)
// + src/data/vo_<id>.json (character timings for the captions).
// Usage (from video/): node scripts/tts.mjs p1 p7 ...   (ids from LINES; no ids = all)
import { execFileSync } from 'node:child_process'
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs'

const VOICE = 'EXAVITQu4vr4xnSDxMaL' // Sarah, same as s1..s8
const SETTINGS = { stability: 0.45, similarity_boost: 0.8, style: 0.15, use_speaker_boost: true }
// story v2 (n*): Brian, a warmer, less synthetic narrator
const NARRATOR = 'nPczCjzI2devNBz1zQrb'
const NARRATOR_SETTINGS = { stability: 0.4, similarity_boost: 0.8, style: 0.35, use_speaker_boost: true }

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
  // criteria cut (Criteria.tsx): one chapter per judging criterion, real footage of the 02:26 UTC run
  a0: 'PLAYER TWO is an AI that plays your game like a hostile tester, finds the bugs, and gets them fixed. This is one live run.',
  a1: 'One: computer use. H drives a real Windows desktop. It sees only the screen and presses keys. No game state, no code. And we stress-tested it with a live mission: imps and zombies hit it forty-seven times, and its health fell from 999 to four hundred and forty-one. It killed three of them, reached the power-up, and reported the bug.',
  a2: 'Two: it works end to end, with no hand-holding. A verifier replays its inputs and checks a hidden engine log. The developer says one sentence: yes, fix it. Then Devin opens a pull request, it is merged, CI rebuilds the game, and a replay proves the fix. Six and a half minutes. And when the game lost keyboard focus, the product took it back by itself.',
  a3: 'Three: usefulness. This bug still ships in Chocolate Doom and Crispy Doom today. Instead of a vague ticket, the developer gets steps, a clip, proof, and a fix to review.',
  a4: 'Four: what is new. We built frame-stepping into the engine, so a slow AI can play a real-time game. H never sees the bug list or the engine log. A hidden oracle checks every finding, and a scripted replay of the same scenario proves the fix.',
  a5: 'Five: you stay in control. Every finding waits for your word, by voice or by button: fix, skip, explain, or stop. Stop ended this run in about a second.',
  a6: 'Built with Devin, powered by H. PLAYER TWO.',
  // story cut (Story.tsx): problem -> idea -> live demo -> the bug -> found, proven, fixed -> potential
  b1: 'Every game ships with bugs. Studios pay big teams of testers to play the same levels for months, and bugs still slip through to players.',
  b2: 'So we built PLAYER TWO: an AI that tests your game the way a player would. It plays, it hunts for bugs, it proves each one, and it gets it fixed.',
  b3: 'To show it, we gave it a real game: Doom. Open source, thirty years old. The AI gets no code and no game data. Only the screen, and a keyboard.',
  b4: 'This is it playing, live, on our laptop. The player is H, a computer-use agent. Monsters attack it. It fights back, and keeps testing.',
  b5: 'And here is what it caught. Invulnerability should turn the whole screen grey. But look at the sky. It stays red. A tiny bug that has survived thirty years of players.',
  b6: 'It writes a bug report, with the steps. Then our verifier replays its exact moves, and the game engine itself confirms the bug.',
  b7: 'The developer says one sentence: yes, fix it. Devin, an AI software engineer, finds the cause, writes the fix, and opens a pull request.',
  b8: "The game is rebuilt, the scenario is replayed, and now the sky turns grey. Found, proven and fixed, six and a half minutes after 'fix it'.",
  b9: "That was one bug, in one night. Now imagine it on a studio's game, as big as GTA 6: hundreds of AI testers playing every build overnight, and every bug arriving with a video, a proof, and a fix ready to review.",
  b10: "PLAYER TWO. Your game's toughest tester.",
  // story cut v2 (Story.tsx): market -> problem -> idea -> live test -> bug -> found/proven/fixed -> kid mode -> potential
  n1: 'Games are the biggest entertainment business on Earth. About two hundred billion dollars a year. Three and a half billion players.',
  n2: 'And every one of those games ships with bugs. Studios spend a big part of every budget on testing: rooms of people, replaying the same levels for months. And bugs still reach the players.',
  n3: 'So we built PLAYER TWO: an AI that tests your game the way a player would. It plays, it hunts for bugs, it proves each one, and it gets it fixed.',
  n4: 'To show it, we gave it a real game: Doom. Open source, thirty years old. The AI gets no code and no game data. Only the screen, and a keyboard.',
  n5: 'This is it playing, live, on our laptop. The player is H, a computer-use agent. Monsters attack it. It fights back, and keeps testing.',
  n6: 'And here is what it caught. Invulnerability should turn the whole screen grey. But look at the sky. It stays red. A tiny bug that has survived thirty years of players.',
  n7: 'It writes a bug report, with the steps. Then our verifier replays its exact moves, and the game engine itself confirms the bug.',
  n8: 'The developer says one sentence: yes, fix it. Devin, an AI software engineer, finds the cause, writes the fix, and opens a pull request.',
  n9: "The game is rebuilt, the scenario is replayed, and now the sky turns grey. Found, proven and fixed, six and a half minutes after 'fix it'.",
  n10: 'And the same eyes can play with you. In kid mode, PLAYER TWO becomes Pixel, a game buddy for children. It sees the screen, hears your voice, and answers. Listen.',
  n11: "That was one bug, on one laptop, in one night. Now point it at a two-hundred-billion-dollar industry. Hundreds of AI testers on every build of a game as big as GTA 6, every night. Every bug arriving with a video, a proof, and a fix ready to review. And for every player, a buddy inside the game.",
  n12: "PLAYER TWO. Your game's toughest tester, and its best friend.",
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
  const story2 = /^n\d+$/.test(id)
  const r = await fetch(`https://api.elevenlabs.io/v1/text-to-speech/${story2 ? NARRATOR : VOICE}/with-timestamps?output_format=mp3_44100_128`, {
    method: 'POST',
    headers: { 'xi-api-key': key, 'content-type': 'application/json' },
    body: JSON.stringify({ text, model_id: 'eleven_multilingual_v2', voice_settings: story2 ? NARRATOR_SETTINGS : SETTINGS }),
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
