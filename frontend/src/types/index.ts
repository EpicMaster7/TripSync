export type User = {id:number;email:string;name:string}
export type Trip = {id:number;name:string;destination:string;timezone:string;start_date:string;end_date:string;owner_id:number}
export type Item = {id:number;trip_id:number;title:string;starts_at:string;ends_at:string;location:string;notes:string;link:string|null;position:number;created_by_id:number|null;owner_id:number|null;source:'manual'|'ics';version:number}
export type Subscription = {id:number;trip_id:number;url:string;status:string;error:string|null;last_fetched_at:string|null}
export type SyncRun = {id:number;subscription_id:number;status:string;started_at:string;finished_at:string|null;created:number;updated:number;deleted:number;error:string|null}
export type Session = {user:User;csrf_token:string}
