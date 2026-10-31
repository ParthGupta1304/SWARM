import {defineConfig} from 'vite';
export default defineConfig({base:'/bazaar/',build:{outDir:'../static',emptyOutDir:true},server:{proxy:{'/market':'http://127.0.0.1:8080'}}});
