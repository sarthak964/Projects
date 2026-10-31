export interface User { id: number; phone: string; name: string | null; role: 'renter' | 'reviewer' | 'admin' }
export interface DemoInfo { demo_mode: boolean; banner: string; payment_notice: string; login_notice: string; inspection_notice: string; ai_notice: string }
export interface Job {
  id: number; renter_id: number; reviewer_id: number | null; address: string; status: string;
  checklist_json: string[] | null; price: number | null; created_at: string;
  report_id?: number | null; check_score?: number | null; payment_status?: string | null;
  photo_review_status?: string | null; appeal_status?: string | null;
}
export interface Page<T> { items: T[]; total: number; limit: number; offset: number }
export interface Report { id: number; notes: string | null; check_score: number | null; ai_generated_summary: string | null }
export interface Photo { round?: 'original' | 'reupload'; id: number; checklist_item: string; url: string }
export interface Notice { id: number; job_id: number; title: string; message: string; is_read: boolean; created_at: string }
