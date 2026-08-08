import { execSync } from 'node:child_process'

export default function globalSetup() {
  execSync('.venv/bin/python scripts/reset_conversations.py', {
    cwd: '../backend',
    stdio: 'pipe',
  })
}
