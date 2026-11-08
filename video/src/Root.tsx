import React from 'react'
import { Composition } from 'remotion'
import { PlayerTwo, TOTAL } from './PlayerTwo'

export const Root: React.FC = () => (
  <Composition id="PlayerTwo" component={PlayerTwo} durationInFrames={TOTAL} fps={30} width={1920} height={1080} />
)
