"""Live cancellation check using native runtimes and no tool approvals."""
import asyncio
import json
import sys
import uuid
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from agent_host.host import AgentHost

async def main():
    host = AgentHost(Path(__file__).resolve().parents[1], auto_install_cline=False)
    responses = {}
    async def capture(message):
        if message.get('id'):
            responses[message['id']] = message
    host.emit = capture
    try:
        for backend in ('codex', 'cline'):
            base = {'backend': backend, 'cwd': str(host.root), 'document_key': 'cancel-smoke-' + uuid.uuid4().hex}
            await host.handle({**base, 'id': 'open', 'method': 'session/open'})
            assert responses['open']['status'] == 'ok', responses['open']
            turn = asyncio.create_task(host.handle({**base, 'id': 'turn', 'method': 'turn/start', 'text': 'Write the integers from 1 to 10000 as text. Do not use any tools.'}))
            if backend == 'codex':
                await asyncio.wait_for(asyncio.shield(turn), 30)
            else:
                await asyncio.sleep(0.5)
            await host.handle({**base, 'id': 'cancel', 'method': 'turn/cancel'})
            assert responses['cancel']['status'] == 'ok', responses['cancel']
            await asyncio.wait_for(turn, 30)
            print(json.dumps({'backend': backend, 'cancel': 'PASS', 'native_stop': responses.get('turn', {}).get('data', {}).get('native', {}).get('stopReason')}), flush=True)
    finally:
        await host.shutdown()

if __name__ == '__main__':
    asyncio.run(main())
