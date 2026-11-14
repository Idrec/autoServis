import axios from 'axios';
export const api = axios.create({baseURL: import.meta.env.VITE_API_URL || '/api/'});
api.interceptors.request.use(config => { const token=localStorage.getItem('access'); if(token) config.headers.Authorization=`Bearer ${token}`; return config; });
let refreshing;
api.interceptors.response.use(r=>r, async error=>{
  const config=error.config;
  if(error.response?.status===401 && !config._retry && !['auth/login/','auth/register/','auth/refresh/'].includes(config.url)){
    config._retry=true;
    try {
      refreshing ||= axios.post(`${api.defaults.baseURL}auth/refresh/`,{refresh:localStorage.getItem('refresh')}).then(r=>{localStorage.setItem('access',r.data.access);return r.data.access;}).finally(()=>{refreshing=null;});
      await refreshing;return api(config);
    } catch { localStorage.removeItem('access');localStorage.removeItem('refresh');window.dispatchEvent(new Event('auth-expired')); }
  } return Promise.reject(error);
});
export const rows=data=>Array.isArray(data)?data:data.results||[];
export async function all(path){let next=path,result=[];while(next){const {data}=await api.get(next);result.push(...rows(data));next=data.next||null;}return result;}
export const errorText=e=>{const d=e.response?.data;if(!d)return 'Serverga ulanib bo‘lmadi. Backend ishlayotganini tekshiring.';return typeof d==='string'?d:Object.entries(d).map(([k,v])=>`${k==='detail'?'':k+': '}${Array.isArray(v)?v.join(', '):v}`).join(' ');};
