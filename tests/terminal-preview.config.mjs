// Development-only QA server. It never connects to a broker or market API.
import {defineConfig} from 'vite';
import {spawn} from 'node:child_process';
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';

export default defineConfig({
  root: resolve('workstation/professional_terminal_static'),
  server: {host:'0.0.0.0',allowedHosts:['terminal.local'],proxy:{'/api':{target:'http://127.0.0.1:8799',changeOrigin:true}}},
  plugins:[{
    name:'jarvis-isolated-test-fixtures',
    configureServer(server) {
      const child=spawn('python3',['-m','tests.terminal_preview'],{cwd:process.cwd(),stdio:'inherit'});
      server.httpServer?.once('close',()=>child.kill());
      process.once('exit',()=>child.kill());
      server.middlewares.use((req,res,next)=>{
        if(req.url?.split('?')[0] === '/lightweight-charts.standalone.production.js') {
          res.setHeader('Content-Type','application/javascript');
          res.end(readFileSync(resolve('workstation/quant_terminal_v2_static/lightweight-charts.standalone.production.js'))); return;
        }
        next();
      });
    },
  }],
});
