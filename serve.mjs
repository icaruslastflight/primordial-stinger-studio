import http from 'node:http';
import {readFile} from 'node:fs/promises';
const port=Number(process.env.STINGER_PORT || 5179);
if(!Number.isInteger(port)||port<1||port>65535) throw Error('STINGER_PORT must be between 1 and 65535');
const html=await readFile(new URL('./index.html',import.meta.url));
const server=http.createServer((req,res)=>{
 if(req.url!=='/'&&req.url!=='/index.html'){res.writeHead(404);res.end('Not found');return;}
 res.writeHead(200,{'Content-Type':'text/html; charset=utf-8','Cache-Control':'no-store','X-Content-Type-Options':'nosniff'});
 res.end(html);
});
server.on('error',error=>{console.error(error.code==='EADDRINUSE'?`Port ${port} is busy. Close the previous launcher or set STINGER_PORT.`:error.message);process.exitCode=1;});
server.listen(port,'127.0.0.1',()=>console.log(`VJTB Stinger Studio: http://127.0.0.1:${port}\nKeep this window open. Ctrl+C stops the studio server.`));
