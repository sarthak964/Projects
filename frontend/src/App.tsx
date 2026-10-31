import {LegacyDisputes} from './LegacyDisputes';
import {NotificationCenter} from './NotificationCenter';
import {About} from './About';
import {InspectionActions} from './InspectionActions';
import {OpenJobs,ReviewerProfile} from './Reviewer';
import {AdminQueues,AdminCase,Suspensions,AdminTools} from './Admin';
import {Support} from './Support';
import { useCallback, useEffect, useRef, useState } from 'react';
import type { FormEvent, ReactNode } from 'react';
import { Link, Navigate, NavLink, Route, Routes, useNavigate, useParams, useLocation } from 'react-router-dom';
import { ApiError, formatDate, formatMoney, humanize, request } from './api';
import type { DemoInfo, Job, Notice, Page, Photo, Report, User } from './types';

type Api = <T>(path: string, init?: RequestInit) => Promise<T>;
const SESSION = 'trustay.demo.token';
const paths: Record<string, string> = { home: 'M3 10 12 3l9 7v11H3z M9 21v-8h6v8', grid: 'M3 3h7v7H3z M14 3h7v7h-7z M3 14h7v7H3z M14 14h7v7h-7z', check: 'm5 12 4 4L19 6', arrow: 'M5 12h14 m-6-6 6 6-6 6', plus: 'M12 5v14 M5 12h14', pin: 'M20 10c0 6-8 11-8 11S4 16 4 10a8 8 0 1 1 16 0Z M12 7v6 M9 10h6', clock: 'M12 8v5l3 2 M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0', bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9 M10 21h4', wallet: 'M3 6h17v15H3z M3 6V3h15v3 M15 11h7v5h-7z', logout: 'M9 4H3v16h6 M10 12h12 m-5-5 5 5-5 5', file: 'M5 2h9l5 5v15H5z M14 2v6h5 M8 12h8 M8 16h6', shield: 'm12 2 9 4v6c0 6-9 10-9 10S3 18 3 12V6z m-5 10 3 3 5-6', close: 'm6 6 12 12 M6 18 18 6' };
function Icon({ name, size = 20 }: { name: string; size?: number }) { return <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true"><path d={paths[name] || paths.file} /></svg>; }
function Logo() { return <span className="brand"><span className="brand-mark"><Icon name="home" size={23} /></span>TruStay<span className="brand-dot">.</span></span>; }
function ErrorBox({ children }: { children: ReactNode }) { return children ? <div className="error" role="alert">{children}</div> : null; }
function Status({ value }: { value: string }) { const tone = ['paid', 'approved'].includes(value) ? 'green' : value === 'verified' ? 'amber' : value === 'refunded' ? 'muted' : 'blue'; return <span className={`status ${tone}`}><i />{humanize(value)}</span>; }
function Modal({ title, close, children }: { title: string; close: () => void; children: ReactNode }) {
  const ref = useRef<HTMLDialogElement>(null);
  useEffect(() => { const dialog = ref.current!; dialog.showModal(); return () => dialog.close(); }, []);
  return <dialog ref={ref} onCancel={event => { event.preventDefault(); close(); }}><div className="modal-heading"><h2>{title}</h2><button className="icon-button" onClick={close} aria-label="Close dialog"><Icon name="close" /></button></div>{children}</dialog>;
}

export default function App() {
  const [token, setToken] = useState(() => sessionStorage.getItem(SESSION));
  const [user, setUser] = useState<User | null>(null);
  const [checking, setChecking] = useState(!!token);
  const [sessionMessage, setSessionMessage] = useState('');
  const [demo, setDemo] = useState<DemoInfo | null>(null);
  useEffect(() => { request<DemoInfo>('/demo-info').then(setDemo).catch(() => {}); }, []);
  const logout = useCallback(() => { sessionStorage.removeItem(SESSION); setToken(null); setUser(null); }, []);
  const api: Api = useCallback(async <T,>(path: string, init?: RequestInit) => {
    try { return await request<T>(path, init, token || undefined); }
    catch (error) { if (error instanceof ApiError && error.status === 401) { logout(); setSessionMessage('Your session ended. Please log in again.'); } throw error; }
  }, [token, logout]);
  useEffect(() => {
    if (!token) { setChecking(false); return; }
    let active = true;
    setChecking(true);
    api<User>('/auth/me').then(value => { if (active) setUser(value); }).catch(error => { if (active) { setSessionMessage((error as Error).message); logout(); } }).finally(() => { if (active) setChecking(false); });
    return () => { active = false; };
  }, [token, api, logout]);
  function signedIn(value: { access_token: string; user: User }) { sessionStorage.setItem(SESSION, value.access_token); setUser(value.user); setToken(value.access_token); setSessionMessage(''); }
  if (checking) return <div className="loading-screen"><Logo /><p>Opening your workspace…</p></div>;
  if (!user || !token) return <Login signedIn={signedIn} message={sessionMessage} demo={demo} />;
  return <Shell user={user} api={api} logout={logout} demo={demo}><Routes>
    <Route path="/dashboard" element={<Dashboard user={user} api={api} />} />
    <Route path="/jobs/:id" element={<JobDetail user={user} api={api} token={token} demo={demo} />} />
    <Route path="/notifications" element={<NotificationCenter api={api} />} />
    <Route path="/ledger" element={<Ledger api={api} user={user} />} />
    <Route path="/open-jobs" element={user.role==='reviewer'?<OpenJobs api={api}/>:<Navigate to="/dashboard" replace/>}/>
    <Route path="/profile" element={user.role==='reviewer'?<ReviewerProfile api={api} user={user}/>:<Navigate to="/dashboard" replace/>}/>
    <Route path="/support" element={user.role==='renter'?<Support api={api}/>:<Navigate to="/dashboard" replace/>}/>
    <Route path="/admin/reviews" element={user.role==='admin'?<AdminQueues key="human" api={api}/>:<Navigate to="/dashboard" replace/>}/>
    <Route path="/admin/appeals" element={user.role==='admin'?<AdminQueues key="appeals" api={api} appeals/>:<Navigate to="/dashboard" replace/>}/>
    <Route path="/admin/cases/:id" element={user.role==='admin'?<AdminCase key="human-case" api={api} token={token}/>:<Navigate to="/dashboard" replace/>}/>
    <Route path="/admin/appeals/:id" element={user.role==='admin'?<AdminCase key="appeal-case" api={api} token={token} appeal/>:<Navigate to="/dashboard" replace/>}/>
    <Route path="/admin/reviewers" element={user.role==='admin'?<Suspensions api={api}/>:<Navigate to="/dashboard" replace/>}/>
    <Route path="/admin/tools" element={user.role==='admin'?<AdminTools api={api}/>:<Navigate to="/dashboard" replace/>}/>
    <Route path="/older-disputes" element={user.role!=='reviewer'?<LegacyDisputes api={api} user={user}/>:<Navigate to="/dashboard" replace/>}/>
    <Route path="/about" element={<About/>}/>
    <Route path="*" element={<Navigate to="/dashboard" replace />} />
  </Routes></Shell>;
}

function Login({ signedIn, message, demo }: { signedIn: (data: { access_token: string; user: User }) => void; message: string; demo: DemoInfo | null }) {
  const [role, setRole] = useState('renter');
  const [phone, setPhone] = useState('9000000001');
  const [name, setName] = useState('');
  const [code, setCode] = useState('');
  const [sent, setSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  async function submit(event: FormEvent) {
    event.preventDefault(); setError(''); setBusy(true);
    try {
      if (!sent) { const response = await request<{ dev_otp: string | null; message: string }>('/auth/request-otp', { method: 'POST', body: JSON.stringify({ phone }) }); if (!response.dev_otp) throw new Error('No development OTP returned. Check that the demo server is running.'); setCode(response.dev_otp); setNotice(response.message); setSent(true); }
      else { signedIn(await request('/auth/verify-otp', { method: 'POST', body: JSON.stringify({ phone, code, role, name:name.trim()||null }) })); }
    } catch (err) { setError((err as Error).message); } finally { setBusy(false); }
  }
  return <div className="login-layout"><section className="login-story"><Logo /><div className="story-content"><span className="eyebrow light">BEFORE YOU MOVE, KNOW MORE.</span><h1>A little more <br />certainty. <br /><em>A better move.</em></h1><p>Get a closer look at your next home, even when you can’t be there.</p><div className="story-process"><span><b>01</b> Tell us what to check</span><span><b>02</b> A local reviewer visits</span><span><b>03</b> Decide with more clarity</span></div></div><div className="moving-moment"><img src="/images/moving-day.jpg" alt="A couple packing for a move, decorative stock photograph"/><span>A new place. A new chapter.</span></div><div className="story-foot"><Icon name="shield" /> Your next chapter, with fewer unknowns.</div></section>
    <main className="login-main"><div className="login-top"><span className="pill">INTERACTIVE DEMO</span><span>Made for peace of mind</span></div><div className="login-form"><span className="eyebrow">WELCOME TO TRUSTAY</span><h2>Make yourself at home.</h2><p className="muted-text">Choose a demo account to explore the inspection journey.</p><div className="account-options">{[['renter', '9000000001', 'Find my peace of mind'], ['reviewer', '9000000002', 'View my assignments'], ['admin', '9999999999', 'Explore the overview']].map(([value, number, subtitle]) => <button key={value} type="button" className={`account-option ${role === value ? 'selected' : ''}`} disabled={busy} onClick={() => { setRole(value); setPhone(number); setSent(false); setCode(''); setError(''); setNotice(''); }}><Icon name={value === 'renter' ? 'home' : value === 'admin' ? 'shield' : 'file'} /><strong>{value[0].toUpperCase() + value.slice(1)}</strong><small>{subtitle}</small></button>)}</div>
      <form onSubmit={submit}>{!sent&&<><label htmlFor="signup-name">Name for a new account (optional)</label><input id="signup-name" autoComplete="name" maxLength={100} value={name} onChange={e=>setName(e.target.value)}/></>}<label htmlFor="phone">Phone number</label><input id="phone" inputMode="tel" autoComplete="tel" value={phone} disabled={sent || busy} maxLength={16} required pattern="\+?[0-9]{10,15}" onChange={event => setPhone(event.target.value)} /><small className="field-help">Pre-filled with a sample account. No SMS is sent.</small>{sent && <><label htmlFor="otp">Development OTP</label><input id="otp" autoComplete="one-time-code" inputMode="numeric" pattern="[0-9]{6}" required value={code} onChange={event => setCode(event.target.value)} maxLength={6} /><div className="dev-note">{notice} We’ve filled it in for this demo.</div></>}
      <ErrorBox>{error || message}</ErrorBox><button className="button primary full" disabled={busy}>{busy ? 'Please wait…' : sent ? 'Enter your workspace' : 'Get development OTP'}<Icon name="arrow" /></button>{sent && <button type="button" className="text-button" disabled={busy} onClick={() => { setSent(false); setCode(''); }}>Use a different number or request a new code</button>}</form>
      <div className="login-disclaimer"><Icon name="shield" /><p>{demo?.payment_notice || 'This is a local demo. Payments and payouts are simulated; no real money moves.'}</p></div></div><footer className="login-footer">Thoughtful inspections. More informed decisions.</footer></main></div>;
}

function Shell({ children, user, api, logout, demo }: { children: ReactNode; user: User; api: Api; logout: () => void; demo: DemoInfo | null }) {
  const [unread, setUnread] = useState(0);
  const location = useLocation();
  useEffect(() => {
    const refresh = () => { api<{ unread_count: number }>('/notifications/unread-count').then(data => setUnread(data.unread_count)).catch(() => {}); };
    refresh(); window.addEventListener('trustay:notifications-updated', refresh);
    return () => window.removeEventListener('trustay:notifications-updated', refresh);
  }, [api, location.pathname]);
  return <div className="app-layout"><aside className="sidebar"><Link to="/dashboard" aria-label="TruStay home"><Logo /></Link><div className="workspace-label">YOUR WORKSPACE</div><nav aria-label="Main navigation"><NavLink to="/dashboard"><Icon name="grid" />{user.role === 'admin' ? 'Overview' : 'My inspections'}</NavLink>{user.role==='reviewer'&&<><NavLink to="/open-jobs"><Icon name="pin"/>Nearby jobs</NavLink><NavLink to="/profile"><Icon name="home"/>My location & profile</NavLink></>}{user.role==='admin'&&<><NavLink to="/admin/reviews"><Icon name="shield"/>Human reviews</NavLink><NavLink to="/admin/appeals"><Icon name="file"/>Appeals</NavLink><NavLink to="/admin/reviewers"><Icon name="home"/>Reviewer standing</NavLink><NavLink to="/admin/tools"><Icon name="grid"/>Admin tools</NavLink></>}{user.role==='renter'&&<NavLink to="/support"><Icon name="file"/>Support</NavLink>}{user.role!=='reviewer'&&<NavLink to="/older-disputes"><Icon name="file"/>30-day disputes</NavLink>}<NavLink to="/notifications"><Icon name="bell" />Notifications{unread > 0 && <span className="count">{unread}</span>}</NavLink><NavLink to="/ledger"><Icon name="wallet" />{user.role === 'admin' ? 'Platform ledger' : 'Payment history'}</NavLink></nav><div className="sidebar-note"><img src="/images/moving-day.jpg" alt="Decorative moving-day photograph" loading="lazy"/><div className="tiny-house"><Icon name="home" size={30} /></div><strong>A clearer picture.<br />A calmer decision.</strong><p>Know the little details before making the big move.</p></div><div className="profile"><span className="avatar">{(user.name || user.role)[0].toUpperCase()}</span><div><strong>{user.name || 'Demo account'}</strong><small>{humanize(user.role)} workspace</small></div><button className="icon-button" onClick={logout} aria-label="Log out"><Icon name="logout" size={18} /></button></div></aside><div className="main-wrap"><header className="topbar"><span>Home <span className="breadcrumb">/ {user.role === 'admin' ? 'Admin workspace' : 'Your workspace'}</span></span><div><span className="demo-tag"><i /> Demo workspace</span><Link to="/notifications" className="icon-button" aria-label="View notifications"><Icon name="bell" /></Link></div></header><div className="demo-banner"><Icon name="shield" size={16} /><span>{demo?.banner || 'TruStay demo — sample inspection workflows and simulated payments.'}</span><span className="banner-extra">No real money moves.</span></div><main className="content">{children}</main><footer className="app-footer"><span>TruStay · A little more certainty.</span><Link to="/about">How to test & photo credits ↗</Link></footer></div></div>;
}

function Dashboard({ user, api }: { user: User; api: Api }) {
  const [data, setData] = useState<Page<Job> | null>(null);
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('');
  const [offset, setOffset] = useState(0);
  const [revision, setRevision] = useState(0);
  const [create, setCreate] = useState(false);
  useEffect(() => { let active = true; setLoading(true); setError(''); setData(null); const endpoint = user.role === 'admin' ? '/admin/jobs' : '/jobs/mine'; api<Page<Job>>(`${endpoint}?limit=6&offset=${offset}${filter ? `&status=${filter}` : ''}`).then(value => { if (active) setData(value); }).catch(err => { if (active) setError(err.message); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, [api, user.role, offset, filter, revision]);
  const items = data?.items || [];
  return <><div className="page-heading"><div><span className="eyebrow">YOUR NEXT CHAPTER STARTS HERE</span><h1>{user.role === 'renter' ? 'A home worth knowing.' : user.role === 'reviewer' ? 'Every detail matters.' : 'The bigger picture.'}</h1><p>Welcome back, {user.name || 'there'}. {user.role === 'renter' ? 'Let’s take the guesswork out of your next move.' : 'Here’s what’s happening with your inspections.'}</p></div>{user.role === 'renter' && <button className="button primary" onClick={() => setCreate(true)}><Icon name="plus" size={18} />New inspection</button>}</div>
    <section className="overview-grid" aria-label="Inspection overview"><div className="welcome-card"><div><span className="eyebrow light">A LITTLE LOCAL KNOWLEDGE</span><h2>See the details. <br />Feel the difference.</h2><p>From a dripping tap to a damp wall,<br />the small things make a home.</p><span className="mini-label"><Icon name="shield" size={15} />Independent inspection workflows</span></div><div className="hero-photo"><img src="/images/house-dusk.jpg" alt="Decorative house at dusk"/></div><img className="hero-orbit" src="/images/isometric-home.svg" alt="" aria-hidden="true"/></div><div className="metric"><span className="metric-icon"><Icon name="file" /></span><span className="metric-label">Inspections found</span><strong>{loading ? '—' : data?.total ?? '—'}</strong><small>{filter ? 'Matching your current filter' : 'In your workspace'}</small></div><div className="metric"><span className="metric-icon amber-bg"><Icon name="clock" /></span><span className="metric-label">Awaiting photo review</span><strong>{loading ? '—' : items.filter(job => job.photo_review_status === 'pending').length}</strong><small>On this page</small></div></section>
    <section className="job-section"><div className="section-heading"><div><h2>Your inspections</h2><p>Every visit, every detail, all in one place.</p></div><button className="text-button" onClick={() => setRevision(value => value + 1)} disabled={loading}>Refresh <Icon name="arrow" size={16} /></button></div><div className="filters" aria-label="Filter inspections">{[['', 'All inspections'], ['requested', 'Requested'], ['verified', 'In review'], ['paid', 'Paid']].map(([value, label]) => <button key={value} className={filter === value ? 'active' : ''} onClick={() => { setFilter(value); setOffset(0); }}>{label}</button>)}</div><ErrorBox>{error}</ErrorBox>{loading ? <div className="empty-state" role="status">Loading your inspections…</div> : !items.length ? <div className="empty-state"><Icon name="home" size={36} /><h3>No inspections here yet.</h3><p>{error ? 'Use Refresh to try again.' : 'Try another filter or create your first inspection.'}</p></div> : <div className="jobs-grid">{items.map(job => <Link to={`/jobs/${job.id}`} className="job-card" key={job.id}><div className="property-image"><img src={job.id%2?'/images/living-room.jpg':'/images/house-dusk.jpg'} alt="Illustrative housing photograph, not inspection evidence" loading="lazy"/><span>Illustrative photo</span></div><div className="job-card-top"><span className="property-symbol"><Icon name="home" size={24} /></span><Status value={job.status} /></div><div className="job-number">INSPECTION #{String(job.id).padStart(3, '0')}</div><h3>{job.address}</h3><p className="location"><Icon name="pin" size={14} />{job.checklist_json?.length || 0} checklist items <span>·</span> {formatDate(job.created_at)}</p><div className="job-progress"><div className={`progress-segment ${job.status !== 'requested' ? 'filled' : ''}`} /><div className={`progress-segment ${!['requested', 'accepted'].includes(job.status) ? 'filled' : ''}`} /><div className={`progress-segment ${['verified', 'paid', 'refunded'].includes(job.status) ? 'filled' : ''}`} /><div className={`progress-segment ${['paid', 'refunded'].includes(job.status) ? 'filled' : ''}`} /></div><div className="job-card-bottom"><div><strong>{formatMoney(job.price)}</strong><small>{job.price == null ? 'Distance-based pricing' : 'Simulated inspection price'}</small></div><span className="round-arrow"><Icon name="arrow" size={18} /></span></div>{job.photo_review_status === 'pending' && <div className="attention-note">{user.role === 'renter' ? 'Your photo review is ready' : 'Awaiting renter photo review'}</div>}</Link>)}</div>}
      {data && data.total > 6 && <div className="pagination"><span>{offset + 1}–{Math.min(offset + 6, data.total)} of {data.total}</span><button className="button secondary" disabled={offset === 0 || loading} onClick={() => setOffset(value => Math.max(0, value - 6))}>Previous</button><button className="button secondary" disabled={offset + 6 >= data.total || loading} onClick={() => setOffset(value => value + 6)}>Next</button></div>}</section><div className="bottom-note"><Icon name="shield" /><div><strong>More information. Less uncertainty.</strong><p>Demo reports illustrate the process. Notes-only AI scores do not certify a property’s actual condition.</p></div></div>{create && <NewInspection api={api} close={() => setCreate(false)} />}</>;
}

function NewInspection({ api, close }: { api: Api; close: () => void }) {
  const [address, setAddress] = useState('');
  const [items, setItems] = useState(['Check walls for cracks or damp patches', 'Check taps for water flow and leaks']);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  async function submit(event: FormEvent) { event.preventDefault(); setError(''); const cleaned = items.map(value => value.trim()); if (cleaned.some(value => !value)) { setError('Give each checklist item a description.'); return; } if (new Set(cleaned.map(value => value.toLowerCase())).size !== cleaned.length) { setError('Each checklist item must be unique.'); return; } setBusy(true); try { const job = await api<Job>('/jobs/', { method: 'POST', body: JSON.stringify({ address: address.trim(), checklist: cleaned }) }); close(); navigate(`/jobs/${job.id}`); } catch (err) { setError((err as Error).message); } finally { setBusy(false); } }
  return <Modal title="Request an inspection" close={() => { if (!busy) close(); }}><form onSubmit={submit}><p className="muted-text">Tell a local reviewer where to go and what matters to you.</p><label htmlFor="address">Property address</label><textarea id="address" required maxLength={500} value={address} onChange={event => setAddress(event.target.value)} placeholder="Building, street, area and city" /><small className="field-help">Use a real, searchable address near New Delhi for the demo. Creating a job calls the address lookup provider.</small><div className="section-heading compact"><label>Inspection checklist</label><span className="muted-text">{items.length}/30</span></div>{items.map((value, index) => <div className="checklist-input" key={index}><span>{String(index + 1).padStart(2, '0')}</span><input aria-label={`Checklist item ${index + 1}`} required maxLength={200} value={value} onChange={event => setItems(current => current.map((item, i) => i === index ? event.target.value : item))} /><button type="button" className="icon-button" aria-label={`Remove item ${index + 1}`} disabled={items.length === 1 || busy} onClick={() => setItems(current => current.filter((_, i) => i !== index))}><Icon name="close" size={15} /></button></div>)}<button type="button" className="text-button" disabled={items.length >= 30 || busy} onClick={() => setItems(current => [...current, ''])}><Icon name="plus" size={16} /> Add checklist item</button><div className="dev-note">The price is calculated when a reviewer accepts. This demo does not collect real money.</div><ErrorBox>{error}</ErrorBox><button className="button primary full" disabled={busy}>{busy ? 'Finding address and creating…' : 'Create inspection'}<Icon name="arrow" size={18} /></button></form></Modal>;
}

function JobDetail({ api, user, token, demo }: { api: Api; user: User; token: string; demo: DemoInfo | null }) {
  const {id}=useParams();
  const[job,setJob]=useState<Job|null>(null);const[report,setReport]=useState<Report|null>(null);const[photos,setPhotos]=useState<Photo[]>([]);
  const[error,setError]=useState('');const[success,setSuccess]=useState('');const[loading,setLoading]=useState(true);const[revision,setRevision]=useState(0);
  useEffect(()=>{let active=true;setLoading(true);setError('');setJob(null);setReport(null);setPhotos([]);(async()=>{
    const value=await api<Job>(`/jobs/${id}`);
    const endpoint=user.role==='admin'?'/admin/jobs':'/jobs/mine';let offset=0;let summary:Job|undefined;
    while(!summary){const page=await api<Page<Job>>(`${endpoint}?limit=100&offset=${offset}`);summary=page.items.find(item=>item.id===value.id);offset+=page.limit;if(!page.items.length||offset>=page.total)break;}
    if(active)setJob({...value,...summary});
    if(user.role==='admin'||user.id===value.renter_id||user.id===value.reviewer_id){
      const rows=await api<Photo[]>(`/jobs/${id}/photos`);if(active)setPhotos(rows);
      if(summary?.report_id){const result=await api<Report>(`/reports/${summary.report_id}`);if(active)setReport(result);}
    }
  })().catch(e=>{if(active)setError(e.message);}).finally(()=>{if(active)setLoading(false);});return()=>{active=false;};},[api,id,user.id,user.role,revision]);
  function changed(message:string){setSuccess(message);setRevision(v=>v+1);window.dispatchEvent(new Event('trustay:notifications-updated'));}
  const participant=job&&(user.role==='admin'||user.id===job.renter_id||user.id===job.reviewer_id);
  return <><Link to="/dashboard" className="back-link">← Back to inspections</Link><ErrorBox>{error}</ErrorBox>{success&&<div className="success" role="status">{success}</div>}{loading?<div className="empty-state">Loading inspection…</div>:job?<>
    <div className="page-heading"><div><span className="eyebrow">INSPECTION #{String(job.id).padStart(3,'0')}</span><h1 className="detail-title">{job.address}</h1><p>Created {formatDate(job.created_at)} · {job.checklist_json?.length||0} checklist items</p></div><Status value={job.status}/></div>
    <div className="detail-grid"><div><section className="panel"><h2>Your inspection checklist</h2>{job.checklist_json?.map((item,index)=><div className="checklist-row" key={item}><span>{String(index+1).padStart(2,'0')}</span><strong>{item}</strong></div>)}</section>
    {report&&<section className="panel"><div className="section-heading"><h2>Inspection report</h2>{report.check_score!=null&&<span className="score">{report.check_score}/100</span>}</div><div className="dev-note">{demo?.inspection_notice||'Demo content is not proof of a real inspection.'}</div><h3>Reviewer’s notes</h3><p className="report-text">{report.notes||'No saved notes.'}</p>{report.ai_generated_summary&&<><h3>Notes assessment</h3><p className="report-text muted-text">{report.ai_generated_summary}</p></>}</section>}
    {participant?<InspectionActions api={api} user={user} job={job} report={report} photos={photos} token={token} onChange={changed}/>:<section className="panel"><p>Accept this request from the nearby jobs page before viewing its protected evidence.</p><Link to="/open-jobs" className="button primary">Nearby jobs</Link></section>}</div>
    <aside>{user.role==='admin'&&job.photo_review_status==='awaiting_human'&&<Link className="button primary full" to={`/admin/cases/${job.id}`}>Review this case</Link>}{user.role==='admin'&&job.appeal_status==='pending'&&<Link className="button primary full" to={`/admin/appeals/${job.id}`}>Review this appeal</Link>}{user.role==='renter'&&!job.photo_review_status&&['paid','disputed'].includes(job.status)&&<Link className="button secondary full" to={`/older-disputes?job=${job.id}`}>Older-job dispute options</Link>}<section className="panel"><span className="eyebrow">INSPECTION SUMMARY</span><div className="summary-price">{formatMoney(job.price)}</div><small className="field-help">{job.price==null?'Price set at reviewer acceptance':'Simulated price · no money collected'}</small><dl><dt>Reviewer</dt><dd>{job.reviewer_id?`Reviewer #${job.reviewer_id}`:'Not assigned'}</dd><dt>Payment</dt><dd>{job.payment_status?humanize(job.payment_status):'Not created'}</dd><dt>Photo review</dt><dd>{job.photo_review_status?humanize(job.photo_review_status):'Not started'}</dd>{job.appeal_status&&<><dt>Appeal</dt><dd>{humanize(job.appeal_status)}</dd></>}</dl><button className="text-button" onClick={()=>setRevision(v=>v+1)}>Refresh inspection</button></section><div className="detail-tip"><Icon name="shield"/><p>Available actions follow your role and the current saved stage.</p></div></aside></div>
  </>:null}</>;
}

function Ledger({ api, user }: { api: Api; user: User }) {
  const [data, setData] = useState<{ net?: number; platform_balance?: number; escrow_balance?: number; balanced?: boolean; entries?: { id: number; job_id: number; kind: string; amount: number; created_at: string }[] } | null>(null);
  const [error, setError] = useState('');
  useEffect(() => { api(user.role === 'admin' ? '/admin/ledger/summary' : '/ledger/me').then(value => setData(value as typeof data)).catch(err => setError(err.message)); }, [api, user.role]);
  return <><div className="page-heading"><div><span className="eyebrow">THE NUMBERS, CLEARLY</span><h1>{user.role === 'admin' ? 'Platform ledger.' : 'Your payment history.'}</h1><p>All amounts are simulated. No real payments, refunds or payouts occur.</p></div></div><ErrorBox>{error}</ErrorBox>{data && <section className="panel"><span className="eyebrow">{user.role === 'admin' ? 'PLATFORM BALANCE' : 'NET SIMULATED MOVEMENT'}</span><div className="summary-price">{formatMoney(data.net ?? data.platform_balance)}</div>{user.role === 'admin' ? <p>Escrow: {formatMoney(data.escrow_balance)} · Ledger balanced: {data.balanced ? 'Yes' : 'No'}</p> : <><small className="field-help">Negative amounts mean money spent; positive amounts mean money received.</small><div className="ledger-table"><table><thead><tr><th>Inspection</th><th>Movement</th><th>Date</th><th>Amount</th></tr></thead><tbody>{data.entries?.map(entry => <tr key={entry.id}><td><Link to={`/jobs/${entry.job_id}`}>#{entry.job_id}</Link></td><td>{humanize(entry.kind)}</td><td>{formatDate(entry.created_at)}</td><td>{formatMoney(entry.amount)}</td></tr>)}</tbody></table>{!data.entries?.length && <p className="empty-state">No payment records yet.</p>}</div></>}</section>}</>;
}
