import React from 'react'
import { Composition } from 'remotion'
import { PlayerTwo, TOTAL } from './PlayerTwo'
import { PlayerTwoPitch, PITCH_TOTAL } from './Pitch'
import { PlayerTwoTight, TIGHT_TOTAL } from './Tight'
import { PlayerTwoReal, REAL_TOTAL } from './Real'
import { PlayerTwoCriteria, CRITERIA_TOTAL } from './Criteria'
import { PlayerTwoStory, STORY_TOTAL } from './Story'

export const Root: React.FC = () => (
  <>
    <Composition id="PlayerTwo" component={PlayerTwo} durationInFrames={TOTAL} fps={30} width={1920} height={1080} />
    <Composition id="PlayerTwoPitch" component={PlayerTwoPitch} durationInFrames={PITCH_TOTAL} fps={30} width={1920} height={1080} />
    <Composition id="PlayerTwoTight" component={PlayerTwoTight} durationInFrames={TIGHT_TOTAL} fps={30} width={1920} height={1080} />
    <Composition id="PlayerTwoStory" component={PlayerTwoStory} durationInFrames={STORY_TOTAL} fps={30} width={1920} height={1080} />
    <Composition id="PlayerTwoCriteria" component={PlayerTwoCriteria} durationInFrames={CRITERIA_TOTAL} fps={30} width={1920} height={1080} />
    <Composition id="PlayerTwoReal" component={PlayerTwoReal} durationInFrames={REAL_TOTAL} fps={30} width={1920} height={1080} />
  </>
)
