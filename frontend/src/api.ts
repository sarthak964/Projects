export class ApiError extends Error {
  status: number;
  constructor(message: string, status: number) { super(message); this.status = status; }
}

export async function request<T>(path: string, init: RequestInit = {}, token?: string): Promise<T> {
  const headers = new Headers(init.headers);
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (init.body && typeof init.body === 'string') headers.set('Content-Type', 'application/json');
  let response: Response;
  try { response = await fetch(`/api${path}`, { ...init, headers }); }
  catch { throw new ApiError('Cannot reach the demo server. Check that run_demo.py is running on port 8001.', 0); }
  let validJson = true;
  const data = await response.json().catch(() => { validJson = false; return null; });
  if (!response.ok) {
    const details = data?.error?.details;
    const fields = Array.isArray(details) ? details.map((d: { field?: string; message?: string }) => `${d.field || 'Input'}: ${d.message || 'Invalid value'}`).join(' Â· ') : '';
    throw new ApiError(fields || data?.error?.message || (typeof data?.detail === 'string' ? data.detail : 'The request could not be completed. Please try again.'), response.status);
  }
  if (!validJson) throw new ApiError('The demo server returned an unexpected response. Please try again.', 502);
  return data as T;
}

export function formatMoney(value: number | null | undefined) {
  return value == null ? 'Set at acceptance' : new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR', maximumFractionDigits: 2 }).format(value);
}
export function formatDate(value: string) {
  const utc = /(?:Z|[+-]\d{2}:\d{2})$/i.test(value) ? value : `${value}Z`;
  return new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' }).format(new Date(utc));
}
export const humanize = (value: string) => value.replaceAll('_', ' ');
