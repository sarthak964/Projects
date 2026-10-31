import type { Job, User } from './types';
export type Api = <T>(path:string, init?:RequestInit)=>Promise<T>;
export interface Review {
  job_id:number; status:string; rejected_items:string[]; fee_amount:number; fee_status:string;
  human_fee_amount:number; human_fee_status:string; ai_verdict: {all_genuine?:boolean;items?:{item:string;photo_check:string;observation?:string;reasoning?:string}[]} | null;
  review_deadline?:string|null; reupload_deadline?:string|null; recheck_deadline?:string|null; ai_result_deadline?:string|null; escalation_reason?:string|null;
}
export interface Appeal {can_appeal:boolean;appeal_status:string|null;human_decision:string|null;decision_notes:string|null;appeal_deadline:string|null;appeal_reason:string|null;appeal_notes:string|null}
export interface Rating {id:number;score:number;comment:string|null}
export interface Profile {user_id:number;home_lat:number|null;home_lng:number|null;rating_avg:number;jobs_completed:number;strikes:number;suspended:boolean;kyc_status:string;deposit_status:string}
export function permissions(user:User,job:Job,review:Review|null) {
  const reviewer=user.role==='reviewer' && user.id===job.reviewer_id;
  const renter=user.role==='renter' && user.id===job.renter_id;
  return {
    reviewer,renter,
    visit:reviewer && job.status==='accepted',
    report:reviewer && ['visited','needs_reupload'].includes(job.status),
    upload:reviewer && (['visited','needs_reupload'].includes(job.status) || job.status==='verified'&&review?.status==='awaiting_reupload'),
    verify:(reviewer||renter||user.role==='admin') && job.status==='report_submitted',
    initialReview:renter && job.status==='verified'&&review?.status==='pending',
    recheck:renter && job.status==='verified'&&review?.status==='awaiting_renter_recheck',
    aiChoice:renter && job.status==='verified'&&review?.status==='ai_checked_genuine',
    rating:renter&&job.status==='paid',
  };
}
export function allowedUploadItems(job:Job, review:Review|null) {return job.status==='verified'&&review?.status==='awaiting_reupload'?review.rejected_items:job.checklist_json||[];}
export const json=(body:unknown):RequestInit=>({method:'POST',body:JSON.stringify(body)});
export function validatePhoto(file:{size:number;name:string}) {if (!file.size) return 'Choose a non-empty image.';if(file.size>8*1024*1024)return 'Each photo must be 8 MiB or smaller.';if(!/\.(jpe?g|png|webp)$/i.test(file.name))return 'Use a JPEG, PNG or WebP image.';return '';}
export function validateNotes(notes:string) {const clean=notes.trim();return clean.length<10||clean.length>10000||!/[\p{L}\p{N}]/u.test(clean)?'Write 10–10,000 characters describing the checklist findings.':'';}
