async function apiGet(url){
  const res = await fetch(url);
  if(!res.ok){ throw new Error((await res.json()).detail || res.statusText); }
  return res.json();
}
async function apiPost(url, body){
  const res = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  if(!res.ok){ throw new Error((await res.json()).detail || res.statusText); }
  return res.json();
}
async function apiPut(url, body){
  const res = await fetch(url, {method:'PUT', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  if(!res.ok){ throw new Error((await res.json()).detail || res.statusText); }
  return res.json();
}
async function apiPatch(url, body){
  const res = await fetch(url, {method:'PATCH', headers:{'Content-Type':'application/json'}, body: JSON.stringify(body)});
  if(!res.ok){ throw new Error((await res.json()).detail || res.statusText); }
  return res.json();
}
async function apiDelete(url){
  const res = await fetch(url, {method:'DELETE'});
  if(!res.ok){ throw new Error((await res.json()).detail || res.statusText); }
  return res.json();
}

function toggleModal(el, show){ el.classList.toggle('show', !!show); }
function showToast(text, isError=false){
  const t = document.getElementById('toast');
  t.textContent = text; t.classList.toggle('error', !!isError);
  t.classList.add('show');
  setTimeout(()=> t.classList.remove('show'), 1600);
}
function escapeHtml(str){
  return str.replace(/[&<>"']/g, s => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;', "'":'&#39;'}[s]));
}
