const { chromium } = require('playwright');
const assert = require('node:assert/strict');
const { pathToFileURL } = require('node:url');
const path = require('node:path');

(async () => {
  const browser = await chromium.launch({channel: 'msedge', headless: true});
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.addInitScript(() => {
      window.calls = [];
      window.sketchup = {ai_dg_action: x => window.calls.push(JSON.parse(x)), ai_dg_ready: () => {}};
    });
    await page.goto(pathToFileURL(path.resolve('bridge_sketchup/ai_dg_bridge/ui/control_center.html')).href);
    assert.deepEqual(await page.locator('nav .tab:visible').allTextContents(), ['Codex', 'Cline', 'Bản vẽ', 'Dựng model', 'Cài đặt']);
    assert.equal(await page.locator('#codex-session').isVisible(), false);
    await page.locator('#codex-text').fill('draft remains');
    await page.evaluate(() => {
      for (const delta of ['Hello', ' world']) window.aiDgReceive({action: 'agent_event', data: {backend: 'codex', event: 'item/agentMessage/delta', data: {itemId: 'item-1', delta}}});
    });
    assert.equal(await page.locator('#codex-text').inputValue(), 'draft remains');
    assert.equal(await page.locator('#codex-history .chat-msg.agent').count(), 1);
    assert.equal(await page.locator('#codex-history .chat-msg.agent .chat-body').textContent(), 'Hello world');
    await page.locator('[data-tab="cline"]').click();
    await page.evaluate(() => window.aiDgReceive({action: 'agent_event', data: {backend: 'cline', event: 'session/update', data: {update: {sessionUpdate: 'agent_message_chunk', content: {type: 'text', text: 'Cline output'}}}}}));
    assert.equal(await page.locator('#cline-history .chat-msg.agent .chat-body').textContent(), 'Cline output');
    await page.locator('select[aria-label="Chế độ Cline"]').selectOption('act');
    assert.equal(await page.evaluate(() => window.calls.at(-1).action), 'agent_set_mode');
    await page.locator('[data-agent-cancel="cline"]').click();
    assert.equal(await page.evaluate(() => window.calls.at(-1).action), 'agent_turn_cancel');
    assert.deepEqual(errors, []);
    console.log('UI_DOM_PASS: tabs, diagnostics hiding, streaming, draft preservation, Plan/Act, cancel');
  } finally {
    await browser.close();
  }
})().catch(error => {console.error(error); process.exitCode = 1;});
