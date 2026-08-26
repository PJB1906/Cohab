import { chromium } from 'playwright'

const OUT = process.argv[2]
const b = await chromium.launch()
const ctx = await b.newContext({ viewport: { width: 1600, height: 1000 } })
const p = await ctx.newPage()

// Log in as the demo account.
await p.goto('http://localhost:5173/login')
await p.waitForTimeout(1200)
await p.fill('input[type="email"]', 'demo@christuniversity.in')
await p.fill('input[type="password"]', 'demo-pass-1234')
await p.click('button[type="submit"]')
await p.waitForTimeout(3500)
console.log('after login:', p.url())

for (const [name, path] of [
  ['matches', '/matches'],
  ['profile', '/profile'],
  ['moderation', '/moderation'],
  ['analytics', '/analytics'],
]) {
  await p.goto('http://localhost:5173' + path)
  await p.waitForTimeout(3000)
  await p.screenshot({ path: `${OUT}/${name}.png` })
  console.log(name, '->', p.url())
}

// Mobile width, questionnaire — the back-button gap.
const m = await ctx.newPage()
await m.setViewportSize({ width: 390, height: 844 })
await m.goto('http://localhost:5173/onboarding/questionnaire')
await m.waitForTimeout(3000)
await m.screenshot({ path: `${OUT}/mobile-questionnaire.png` })

await b.close()
