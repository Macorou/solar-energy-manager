import {defineConfig} from 'vitest/config'
export default defineConfig({server:{port:5173,proxy:{'/api':'http://127.0.0.1:8080'}},test:{environment:'jsdom',globals:true}})
