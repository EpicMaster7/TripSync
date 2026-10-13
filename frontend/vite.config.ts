import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
export default defineConfig({plugins:[react()],server:{host:'0.0.0.0',proxy:{
  '/auth':'http://backend:8000','/me':'http://backend:8000','/trips':'http://backend:8000',
  '/invites':'http://backend:8000','/health':'http://backend:8000',
  '/ws':{target:'ws://backend:8000',ws:true}
}}})
