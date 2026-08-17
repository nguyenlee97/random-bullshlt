import assert from 'node:assert/strict'
import test from 'node:test'

import {
  assignmentPlatform,
  assignmentRole,
  bestCreativeForZone,
  creativeAssignmentIdentityScore,
  highConfidenceCreativeIdentity,
} from '../src/lib/creativeAssignmentIdentity.js'

const files = [
  { id: 'box', name: 'ai-zuma-box-campaign.png', formatId: 'zuma-box' },
  { id: 'znews-side', name: 'znews-side-banner.png', formatId: 'znews-side-banner' },
  { id: 'baomoi-left', name: 'zuma-Left.png', formatId: 'zuma-Left' },
  { id: 'baomoi-right', name: 'zuma-Right.png', formatId: 'zuma-Right' },
]

test('normalizes platform and placement role aliases', () => {
  assert.equal(assignmentPlatform('ZingNews_Shopping_SideLeft'), 'znews')
  assert.equal(assignmentPlatform('zuma-Right.png'), 'baomoi')
  assert.equal(assignmentRole('znews-side-banner.png'), 'side')
  assert.equal(assignmentRole('BaoMoi_Shopping_SideRight'), 'side_right')
})

test('ZNews side placement prefers ZNews side creative over BaoMoi and box assets', () => {
  const zone = {
    id: 'Znews_ShoppingEcommerce_SideLeft',
    platform: 'Znews',
    format: 'skin',
    size: 'skin',
    creativeContractId: 'znews-category-side-left-v1',
  }

  assert.equal(bestCreativeForZone(files, zone)?.id, 'znews-side')
  assert.ok(
    creativeAssignmentIdentityScore(files[1], zone)
      > creativeAssignmentIdentityScore(files[2], zone),
  )
  assert.ok(creativeAssignmentIdentityScore(files[0], zone) < 0)
})

test('BaoMoi right placement prefers the right BaoMoi creative', () => {
  const zone = {
    id: 'BaoMoi_ShoppingEcommerce_SideRight',
    platform: 'BaoMoi',
    format: 'skin',
    size: 'skin',
    creativeContractId: 'baomoi-category-side-right-v1',
  }

  assert.equal(bestCreativeForZone(files, zone)?.id, 'baomoi-right')
  assert.ok(
    creativeAssignmentIdentityScore(files[3], zone)
      > creativeAssignmentIdentityScore(files[2], zone),
  )
  assert.ok(
    creativeAssignmentIdentityScore(files[3], zone)
      > creativeAssignmentIdentityScore(files[1], zone),
  )
})

test('generic creative names stay neutral for geometry-based fallback', () => {
  assert.equal(
    creativeAssignmentIdentityScore(
      { name: 'campaign-final.png' },
      { id: 'Znews_ShoppingEcommerce_SideLeft' },
    ),
    0,
  )
})

test('shared category background contract treats canonical format as high confidence', () => {
  const zone = {
    id: 'BaoMoi_GamingEsports_Background',
    platform: 'BaoMoi',
    creativeContractId: 'category-background-v1',
  }
  const shared = {
    id: 'shared-background',
    name: 'znews-Background.png',
    formatId: 'znews-Background',
  }

  assert.equal(highConfidenceCreativeIdentity(shared, zone), true)
  assert.equal(bestCreativeForZone([files[2], shared], zone)?.id, 'shared-background')
})
