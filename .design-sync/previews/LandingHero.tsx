import * as React from 'react'
import { LandingHero } from 'agent-frontend'

// Hero cần gradient nền của trang → dùng đúng class .public-landing-v2.
const heroPlane: React.CSSProperties = { background: '#020817', color: '#fff' }

export const HeadlineVietnamese = () => (
  <div className="public-landing-v2" style={heroPlane}>
    <LandingHero onEnterAgent={() => {}} onOpenDemo={() => {}} />
  </div>
)

export const HeadlineMakeYourCampaignMove = () => (
  <div className="public-landing-v2" style={heroPlane}>
    <LandingHero
      title={<>Make your<br /><em>campaign move.</em></>}
      onEnterAgent={() => {}}
      onOpenDemo={() => {}}
    />
  </div>
)
