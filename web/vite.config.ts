import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { spawn, type ChildProcess } from 'child_process'
import path from 'path'
import { fileURLToPath } from 'url'
import net from 'net'

const __dirname = path.dirname(fileURLToPath(import.meta.url))

// Check if port is in use by trying to connect to it
function isPortInUse(port: number): Promise<boolean> {
  return new Promise((resolve) => {
    const socket = new net.Socket()
    socket.setTimeout(1000)
    socket.once('connect', () => {
      socket.destroy()
      resolve(true)
    })
    socket.once('timeout', () => {
      socket.destroy()
      resolve(false)
    })
    socket.once('error', () => {
      socket.destroy()
      resolve(false)
    })
    socket.connect(port, '127.0.0.1')
  })
}

// Plugin to auto-start backend
function backendPlugin() {
  let backendProcess: ChildProcess | null = null

  return {
    name: 'backend-starter',
    async configureServer() {
      // Check if backend is already running
      const portInUse = await isPortInUse(8001)
      if (portInUse) {
        console.log('\n[Backend] Port 8001 already in use, skipping auto-start\n')
        return
      }

      // Start backend using Windows Python venv
      const pythonPath = path.resolve(__dirname, '../.venv/Scripts/python.exe')
      const cwd = path.resolve(__dirname, '..')

      console.log('[Backend] Starting backend server...')
      backendProcess = spawn(pythonPath, ['-m', 'uvicorn', 'src.app:app', '--host', '127.0.0.1', '--port', '8001'], {
        cwd,
        stdio: 'pipe',
      })

      backendProcess.stdout?.on('data', (data) => {
        console.log(`[Backend] ${data.toString().trim()}`)
      })

      backendProcess.stderr?.on('data', (data) => {
        console.error(`[Backend] ${data.toString().trim()}`)
      })

      backendProcess.on('error', (err) => {
        console.error('[Backend] Failed to start:', err.message)
      })

      backendProcess.on('exit', (code) => {
        if (code !== 0 && code !== null) {
          console.error(`[Backend] Exited with code ${code}`)
        }
      })

      // Cleanup on Vite exit
      process.on('exit', () => {
        if (backendProcess) {
          backendProcess.kill()
        }
      })

      process.on('SIGINT', () => {
        if (backendProcess) {
          backendProcess.kill()
        }
        process.exit()
      })

      process.on('SIGTERM', () => {
        if (backendProcess) {
          backendProcess.kill()
        }
        process.exit()
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), tailwindcss(), backendPlugin()],
  server: {
    port: 3000,
    proxy: {
      '/api': 'http://localhost:8001',
      '/health': 'http://localhost:8001',
    },
  },
})
