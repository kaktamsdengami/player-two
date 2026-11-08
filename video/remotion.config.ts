import { Config } from '@remotion/cli/config'

Config.setVideoImageFormat('jpeg')
Config.setJpegQuality(95)
Config.setConcurrency(4)
// Remotion's own headless shell download fails on the stage laptop: use the installed Chrome.
if (process.platform === 'win32') Config.setBrowserExecutable('C:/Program Files/Google/Chrome/Application/chrome.exe')
