import { describe, expect, it } from 'vitest'
import * as dashboard from '../dashboard'
import * as points from '../points'
import * as inspirations from '../inspirations'
import * as referral from '../referral'

describe('barrel exports', () => {
  it('re-exports dashboard components', () => {
    expect(dashboard.DashboardPageHeader).toBeDefined()
    expect(dashboard.DashboardSearchBar).toBeDefined()
    expect(dashboard.DashboardFilterPills).toBeDefined()
    expect(dashboard.DashboardEmptyState).toBeDefined()
  })

  it('re-exports points, inspirations, and referral components', () => {
    expect(points.PointsBalance).toBeDefined()
    expect(points.DailyCheckIn).toBeDefined()
    expect(points.EarnOpportunities).toBeDefined()
    expect(points.PointsHistory).toBeDefined()
    expect(points.RedeemProModal).toBeDefined()

    expect(inspirations.InspirationCard).toBeDefined()
    expect(inspirations.InspirationDetailDialog).toBeDefined()
    expect(inspirations.InspirationGrid).toBeDefined()

    expect(referral.InviteCodeCard).toBeDefined()
    expect(referral.InviteCodeList).toBeDefined()
    expect(referral.ReferralStats).toBeDefined()
  })
})
