#!/usr/bin/env bash
# Clips for PlayerTwoCriteria (src/Criteria.tsx), from the desktop screen recording of the 02:26 UTC run.
# Recording time t = UTC - 02:25:32. Run from video/ after scripts/cut_real.sh (reuses v4/c6 and v4/pr, v4/live).
set -euo pipefail
M="${1:-/c/Users/mitya/Videos/player-two-live-0325.mkv}"
O=public/v5
mkdir -p "$O"
enc=(-c:v libx264 -crf 18 -preset veryfast -pix_fmt yuv420p -an -r 30)
A="crop=1920:740:0:60"   # game window + dashboard
ffmpeg -v error -y -ss 494 -t 9 -i "$M" -vf "$A" "${enc[@]}" "$O/open.mp4"                  # power-up, real time
ffmpeg -v error -y -ss 290 -t 50 -i "$M" -vf "$A,setpts=PTS/2" "${enc[@]}" "$O/fight.mp4"    # imp fight, 2x
ffmpeg -v error -y -ss 700 -t 30 -i "$M" -vf "$A,setpts=PTS/6" "${enc[@]}" "$O/verify.mp4"   # verifier, 6x
ffmpeg -v error -y -ss 787 -t 9 -i "$M" -vf "crop=940:960:980:60" "${enc[@]}" "$O/ask.mp4"   # "Yes, fix it."
ffmpeg -v error -y -ss 200 -t 16 -i "$M" -vf "$A" "${enc[@]}" "$O/think.mp4"                 # frame-step, real time
ffmpeg -v error -y -ss 1489 -t 9 -i "$M" -vf "crop=600:960:1320:60" "${enc[@]}" "$O/stop.mp4" # Stop button
ffmpeg -v error -y -ss 651.5 -i "$M" -frames:v 1 -vf "$A" "$O/focus.png"                      # focus guard banner
ffmpeg -v error -y -ss 7.5 -i "$O/ask.mp4" -frames:v 1 "$O/buttons.png"
cp public/v4/c6.mp4 "$O/proof.mp4"
