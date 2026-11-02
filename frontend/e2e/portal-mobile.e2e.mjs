// End-to-end check of the Service Request workflow on mobile + the staff ticket view on desktop.
//
//   BASE_URL=http://localhost:5173 node e2e/portal-mobile.e2e.mjs
//
// Requires the frontend (vite dev or a production build behind Nginx) and the API to be running,
// plus an admin account (ADMIN_USER / ADMIN_PASS, default admin / Admin-Pass-2026) that does not
// need to change its password. Exits non-zero on failure. Screenshots go to SCREEN_DIR.
import { createRequire } from 'node:module'
import { mkdirSync } from 'node:fs'
import path from 'node:path'

const require = createRequire(import.meta.url)
let pw
try {
  pw = require('playwright')
} catch {
  pw = require('/opt/node-tools/node_modules/playwright')
}
const { chromium, devices, request } = pw

const BASE = (process.env.BASE_URL ?? 'http://localhost:5173').replace(/\/$/, '')
const ADMIN_USER = process.env.ADMIN_USER ?? 'admin'
const ADMIN_PASS = process.env.ADMIN_PASS ?? 'Admin-Pass-2026'
// Set E2E_IGNORE_HTTPS_ERRORS=1 when testing a deployment that uses a self-signed certificate.
const IGNORE_HTTPS = process.env.E2E_IGNORE_HTTPS_ERRORS === '1'
const SHOTS = process.env.SCREEN_DIR ?? path.resolve('e2e/output')
mkdirSync(SHOTS, { recursive: true })

let failures = 0
const log = (...a) => console.log('·', ...a)
function check(cond, msg) {
  if (!cond) {
    failures += 1
    console.error('✗', msg)
  } else console.log('✓', msg)
}
async function shot(page, name) {
  await page.screenshot({ path: path.join(SHOTS, `${name}.png`), fullPage: true })
}
async function noHorizontalScroll(page, label) {
  const { sw, iw } = await page.evaluate(() => ({ sw: document.documentElement.scrollWidth, iw: window.innerWidth }))
  check(sw <= iw + 1, `${label}: no horizontal scroll (scrollWidth ${sw} <= ${iw})`)
}

/** Create distinct JPEG/PNG files in the browser (canvas) so the server sees real images. */
async function makeImages(page, count, offset) {
  const list = await page.evaluate(
    async ({ count, offset }) => {
      const out = []
      for (let i = 0; i < count; i++) {
        const n = offset + i
        const c = document.createElement('canvas')
        c.width = 640
        c.height = 480
        const ctx = c.getContext('2d')
        ctx.fillStyle = `hsl(${(n * 47) % 360} 70% 55%)`
        ctx.fillRect(0, 0, 640, 480)
        ctx.fillStyle = '#fff'
        ctx.font = 'bold 120px sans-serif'
        ctx.fillText(`#${n}`, 180, 290)
        const png = n % 3 === 0
        const url = c.toDataURL(png ? 'image/png' : 'image/jpeg', 0.85)
        out.push({ name: `equipment-${n}.${png ? 'png' : 'jpg'}`, mimeType: png ? 'image/png' : 'image/jpeg', b64: url.split(',')[1] })
      }
      return out
    },
    { count, offset },
  )
  return list.map((f) => ({ name: f.name, mimeType: f.mimeType, buffer: Buffer.from(f.b64, 'base64') }))
}

function yesterday() {
  const d = new Date(Date.now() - 36 * 3600 * 1000)
  return d.toISOString().slice(0, 10)
}

async function mobileFlow(browser, deviceName) {
  const tag = deviceName.replace(/\s+/g, '-').toLowerCase()
  const ctx = await browser.newContext({ ...devices[deviceName], locale: 'th-TH', ignoreHTTPSErrors: IGNORE_HTTPS })
  const page = await ctx.newPage()
  page.on('pageerror', (e) => {
    failures += 1
    console.error('✗ page error:', e.message)
  })
  log(`[${deviceName}] open portal`)
  await page.goto(`${BASE}/`)
  await page.getByRole('heading', { name: 'BUC Customer Service Center' }).waitFor()
  check(await page.getByText('ยินดีต้อนรับสู่ระบบบริการลูกค้า บริษัท บางกอกยูนิเทรด จำกัด').isVisible(), `[${deviceName}] welcome message`)
  check((await page.locator('a[href^="/request/"]').count()) === 6, `[${deviceName}] six service categories`)
  await noHorizontalScroll(page, `[${deviceName}] home`)
  await shot(page, `${tag}-01-home`)

  await page.locator('a[href="/request/service"]').click()
  await page.locator('#f-organization').waitFor()
  // Step 1 — contact
  await page.locator('[data-testid=next-step]').click()
  check(await page.getByText('กรุณากรอกข้อมูลนี้').first().isVisible(), `[${deviceName}] required-field validation shown`)
  await page.fill('#f-organization', 'โรงพยาบาลทดสอบ E2E')
  await page.selectOption('#f-organization_type', 'GOV_HOSPITAL')
  await page.fill('#f-department', 'ICU')
  await page.fill('#f-contact_name', 'ผู้ทดสอบ อัตโนมัติ')
  await page.fill('#f-phone', '081-234-5678')
  await page.fill('#f-email', 'e2e@example.com')
  await noHorizontalScroll(page, `[${deviceName}] form step 1`)
  await shot(page, `${tag}-02-form-step1`)
  await page.locator('[data-testid=next-step]').click()

  // Step 2 — equipment details
  await page.locator('#f-equipment_name').waitFor()
  await page.selectOption('#f-equipment_type', 'MEDICAL_DEVICE')
  await page.fill('#f-equipment_name', 'Infusion Pump')
  await page.fill('#f-brand', 'SampleMed')
  await page.fill('#f-model', 'IP-200')
  await page.fill('#f-serial_number', `E2E-${Date.now()}`)
  await page.fill('#f-install_location', 'อาคาร 1 ชั้น 3')
  await page.selectOption('#f-problem_type', 'EQUIPMENT_FAILURE')
  await page.fill('#f-problem_description', 'ทดสอบอัตโนมัติ: เครื่องมีเสียงเตือนตลอดเวลา')
  await page.fill('#f-problem_date', yesterday())
  await page.getByText('สูง - กระทบการให้บริการ').click()

  const counter = page.locator('[data-testid=upload-counter]')
  check((await counter.textContent()).includes('0/10'), `[${deviceName}] counter starts at 0/10`)
  check(await page.getByText('แนบรูปภาพได้สูงสุด 10 ภาพ').isVisible(), `[${deviceName}] max images hint`)
  check((await page.locator('[data-testid=camera-input]').getAttribute('capture')) === 'environment', `[${deviceName}] camera input uses capture`)

  await page.setInputFiles('[data-testid=gallery-input]', await makeImages(page, 3, 1))
  await page.waitForFunction(() => document.querySelector('[data-testid=upload-counter]')?.textContent?.includes('3/10'))
  check((await page.locator('[data-testid=upload-previews] img').count()) === 3, `[${deviceName}] 3 previews shown, counter 3/10`)
  await shot(page, `${tag}-03-uploader-3`)

  await page.setInputFiles('[data-testid=gallery-input]', await makeImages(page, 9, 10))
  await page.waitForFunction(() => document.querySelector('[data-testid=upload-counter]')?.textContent?.includes('10/10'))
  check(await page.locator('[data-testid=upload-warning]').isVisible(), `[${deviceName}] over-limit warning shown`)
  check((await page.locator('[data-testid=upload-warning]').textContent()).includes('2'), `[${deviceName}] warning mentions 2 excess files`)
  check((await page.locator('[data-testid=upload-previews] img').count()) === 10, `[${deviceName}] capped at 10 images`)
  check(await page.locator('[data-testid=add-files]').isDisabled(), `[${deviceName}] add button disabled when full`)
  await shot(page, `${tag}-04-uploader-full`)

  await page.locator('[data-testid=remove-file]').first().click()
  await page.waitForFunction(() => document.querySelector('[data-testid=upload-counter]')?.textContent?.includes('9/10'))
  check(true, `[${deviceName}] removed one image -> 9/10`)
  await noHorizontalScroll(page, `[${deviceName}] form step 2`)
  await page.locator('[data-testid=next-step]').click()

  // Step 3 — review + consent
  await page.getByText('ตรวจสอบข้อมูลก่อนส่ง').waitFor()
  await page.locator('[data-testid=submit-request]').click()
  check(await page.getByText('กรุณายอมรับประกาศความเป็นส่วนตัว').first().isVisible(), `[${deviceName}] consent required`)
  await page.locator('[data-testid=privacy-consent]').check()
  await shot(page, `${tag}-05-review`)
  await page.locator('[data-testid=submit-request]').click()

  await page.waitForURL(/\/request\/service\/success/, { timeout: 60_000 })
  const number = (await page.locator('[data-testid=ticket-number]').textContent()).trim()
  check(/^BUC-SRV-\d{4}-\d{5}$/.test(number), `[${deviceName}] ticket number ${number}`)
  const trackingUrl = (await page.locator('[data-testid=tracking-url]').textContent()).trim()
  check(trackingUrl.includes(`/track/${number}#t=`), `[${deviceName}] tracking link uses #t= fragment`)
  await noHorizontalScroll(page, `[${deviceName}] success`)
  await shot(page, `${tag}-06-success`)

  await page.locator('[data-testid=open-tracking]').click()
  await page.locator('[data-testid=tracking-status]').waitFor()
  check((await page.locator('[data-testid=tracking-status]').textContent()).includes('รับเรื่องใหม่'), `[${deviceName}] tracking shows status รับเรื่องใหม่`)
  await noHorizontalScroll(page, `[${deviceName}] tracking`)
  await shot(page, `${tag}-07-tracking`)

  // Wrong token must not reveal anything.
  await page.goto(`${BASE}/track/${number}#t=wrongtokenwrongtoken`)
  await page.getByText('ไม่พบข้อมูล').first().waitFor()
  check(true, `[${deviceName}] wrong tracking token rejected`)
  await ctx.close()
  return number
}

async function desktopFlow(browser, ticketNumber) {
  const ctx = await browser.newContext({ viewport: { width: 1440, height: 900 }, locale: 'th-TH', ignoreHTTPSErrors: IGNORE_HTTPS })
  const page = await ctx.newPage()
  page.on('pageerror', (e) => {
    failures += 1
    console.error('✗ page error:', e.message)
  })
  log('[desktop] staff login')
  await page.goto(`${BASE}/admin`)
  await page.waitForURL(/\/admin\/login/)
  await page.fill('#username', ADMIN_USER)
  await page.fill('#password', ADMIN_PASS)
  await page.getByRole('button', { name: 'เข้าสู่ระบบ' }).click()
  await page.getByRole('heading', { name: 'แดชบอร์ด' }).waitFor()
  await page.locator('.recharts-surface').first().waitFor()
  check(true, '[desktop] dashboard loaded with charts')
  await page.waitForTimeout(600)
  await shot(page, 'desktop-01-dashboard')

  await page.goto(`${BASE}/admin/tickets`)
  await page.locator('table.table-base tbody tr').first().waitFor()
  await shot(page, 'desktop-02-ticket-list')
  await page.goto(`${BASE}/admin/tickets?q=${encodeURIComponent(ticketNumber)}`)
  await page.getByRole('link', { name: ticketNumber }).click()
  await page.locator('[data-testid=detail-ticket-number]').waitFor()
  check((await page.locator('[data-testid=detail-ticket-number]').textContent()).trim() === ticketNumber, '[desktop] ticket detail opened')

  const gallery = page.locator('[data-testid=attachment-gallery] img')
  await gallery.first().waitFor()
  const count = await gallery.count()
  check(count === 9, `[desktop] gallery shows ${count} images (expected 9)`)
  await page.waitForFunction(() => [...document.querySelectorAll('[data-testid=attachment-gallery] img')].every((i) => i.complete && i.naturalWidth > 0))
  check(true, '[desktop] all gallery thumbnails loaded')
  await shot(page, 'desktop-03-ticket-detail')

  await gallery.first().click()
  const viewer = page.locator('[data-testid=image-viewer]')
  await viewer.waitFor()
  await page.waitForFunction(() => {
    const img = document.querySelector('[data-testid=image-viewer] img')
    return img && img.complete && img.naturalWidth > 0
  })
  check(await viewer.getByText('1 / 9').isVisible(), '[desktop] full-screen viewer opened (1 / 9)')
  await page.keyboard.press('ArrowRight')
  check(await viewer.getByText('2 / 9').isVisible(), '[desktop] viewer keyboard navigation')
  await shot(page, 'desktop-04-image-viewer')
  await page.keyboard.press('Escape')
  await viewer.waitFor({ state: 'detached' })

  const src = await gallery.first().getAttribute('src')
  await page.goto(`${BASE}/admin/integrations`)
  await page.getByText('LINE Official Account').first().waitFor()
  await shot(page, 'desktop-05-admin-integrations')
  await ctx.close()
  return src
}

const browser = await chromium.launch()
try {
  const numbers = []
  for (const d of ['iPhone 13', 'Pixel 7']) numbers.push(await mobileFlow(browser, d))
  const attachmentUrl = await desktopFlow(browser, numbers[numbers.length - 1])
  const anon = await request.newContext({ ignoreHTTPSErrors: IGNORE_HTTPS })
  const res = await anon.get(`${BASE}${attachmentUrl}`)
  check(res.status() === 401, `[security] anonymous attachment request -> ${res.status()} (expected 401)`)
  await anon.dispose()
} catch (e) {
  failures += 1
  console.error('✗ exception:', e)
} finally {
  await browser.close()
}
console.log(failures ? `\nFAILED (${failures})` : '\nALL CHECKS PASSED')
process.exit(failures ? 1 : 0)
