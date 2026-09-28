const BASE=process.env.NEXT_PUBLIC_API_BASE_URL||"http://localhost:8000";
export async function api<T>(path:string,init?:RequestInit):Promise<T>{
  const res=await fetch(`${BASE}${path}`,{cache:"no-store",...init,headers:{"Content-Type":"application/json",...(init?.headers||{})}});
  const text=await res.text(); let data:any={}; try{data=text?JSON.parse(text):{}}catch{data={detail:text}};
  if(!res.ok) throw new Error(data?.detail||`API ${res.status}`);
  return data as T;
}