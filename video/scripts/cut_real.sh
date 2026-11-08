#!/usr/bin/env bash
# Clips for PlayerTwoReal (src/Real.tsx), cut from the desktop screen recording of the 02:26 UTC live run.
# Recording time t = UTC - 02:25:32 (narration 02:38:32 = t 780, "Yes, fix it." 02:38:44 = t 792).
# Crops keep only the game window and the dashboard (no other windows on screen). Run from video/.
set -euo pipefail
M="${1:-/c/Users/mitya/Videos/player-two-live-0325.mkv}"
O=public/v4
mkdir -p "$O"
enc=(-c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p -an -r 30)
ffmpeg -v error -y -ss 58 -t 430 -i "$M" -vf "crop=1920:740:0:60,setpts=PTS/16" "${enc[@]}" "$O/c1.mp4"   # H plays, 16x
ffmpeg -v error -y -ss 490 -t 30 -i "$M" -vf "crop=1920:740:0:60,setpts=PTS/2" "${enc[@]}" "$O/c2.mp4"    # power-up, 2x
ffmpeg -v error -y -ss 663 -t 116 -i "$M" -vf "crop=1920:740:0:60,setpts=PTS/10" "${enc[@]}" "$O/c3.mp4"  # verifier, 10x
ffmpeg -v error -y -ss 779 -t 21 -i "$M" -vf "crop=940:960:980:60" "${enc[@]}" "$O/c4.mp4"                # narration + "fix it"
ffmpeg -v error -y -ss 1174.55 -t 6.65 -i "$M" -vf "crop=880:690:0:0" "${enc[@]}" "$O/c6.mp4"             # proof replay
cp ../recordings/20261108-032604-session/voice/F1_narration.mp3 "$O/narration.mp3"
# kid mode: raise the player's (quiet) mic lines ~15 dB
ffmpeg -v error -y -i public/kid_team.mp4 -c:v copy -af "volume=enable='between(t,0,1.0)+between(t,7.1,8.1)+between(t,16.6,18.0)+between(t,30.0,32.1)':volume=6,alimiter=limit=0.9" -c:a aac -b:a 192k public/kid_team_boost.mp4
# real pages (headless Chrome)
C="/c/Program Files/Google/Chrome/Application/chrome.exe"
"$C" --headless=new --disable-gpu --hide-scrollbars --window-size=1600,1000 --force-device-scale-factor=1.2 --screenshot="$(cygpath -w "$PWD/$O/pr.png")" https://github.com/kaktamsdengami/chocolate-doom/pull/5
"$C" --headless=new --disable-gpu --hide-scrollbars --window-size=1600,1000 --virtual-time-budget=15000 --screenshot="$(cygpath -w "$PWD/$O/live.png")" https://player-two-doom.lovable.app
