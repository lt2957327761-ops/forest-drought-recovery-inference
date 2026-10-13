"""Verify frozen EI results from archived products, without fitting or model loading.

H and H-1 scores are recomputed only to check the accepted stored scores.
No output may overwrite the input archive. No bootstrap or event identification.
This is an artifact-level verification path, not an upstream raw-data pipeline.
"""
from pathlib import Path
import argparse,csv,json,math,hashlib,sys,platform
import numpy as np
import pyarrow.parquet as pq
SCALES=['D1','D3','D6'];TOL=1e-12
EXPECTED_MODELS={'D1':'5654d48de03b7c67841be973e0d5aa8fee4c8672f75ce92987340df131109fce','D3':'2e57fb43ee84a570c204a800f59b41c032477e928925e25f81007756ff314fad','D6':'8b44d41c948445a28d38df57b6e40d1200b220ff5e4e56100823fc4aa096a013'}
def csvrows(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return [{k.lstrip('\ufeff'):v for k,v in r.items()} for r in csv.DictReader(f)]
def number(x):
 try:return float(x)
 except (TypeError,ValueError):return math.nan
def same(a,b):
 a,b=number(a),number(b)
 return (math.isnan(a) and math.isnan(b)) or abs(a-b)<=TOL
def month(s):
 y,m=map(int,s.split('-'));return y*12+m-1
def score_lengths(h):
 if not math.isfinite(float(h)) or int(h)!=h or h<1:raise ValueError('Invalid frozen horizon')
 return min(int(h),240),min(max(int(h)-1,0),240),'CAP_TRUNCATED' if h>241 else 'CAP_BOUNDARY_241' if h==241 else 'UNCAPPED'
def frozen_scores(q,h):
 a,b,flag=score_lengths(h);q=np.asarray(q,dtype=float)
 if len(q)!=a or not np.isfinite(q).all() or np.any((q<0)|(q>1)):raise ValueError('Invalid frozen monthly probabilities')
 return float(np.prod(1-q)),float(np.prod(1-q[:b])),flag
def auc(y,p):
 y=np.asarray(y,int);p=np.asarray(p,float)
 if len(y)<20 or len(set(y.tolist()))!=2:return math.nan
 order=np.argsort(p,kind='mergesort');ranks=np.empty(len(p),float);i=0
 while i<len(p):
  j=i+1
  while j<len(p) and p[order[j]]==p[order[i]]:j+=1
  ranks[order[i:j]]=(i+1+j)/2;i=j
 n1=int(y.sum());n0=len(y)-n1;return float((ranks[y==1].sum()-n1*(n1+1)/2)/(n1*n0))
def median_finite(x):
 x=sorted(v for v in x if math.isfinite(v));n=len(x)
 return math.nan if not n else x[n//2] if n%2 else (x[n//2-1]+x[n//2])/2
def grade(n,er,lo,a):
 return 'SUPPORTED' if n>=300 and math.isfinite(lo) and lo>1 and math.isfinite(a) and a>=.6 else 'CONDITIONAL' if n>=100 and ((math.isfinite(er) and er>1) or (math.isfinite(a) and a>=.6)) else 'LIMITED'
def verify(root):
 U=root/'09_EI_UPDATE';checks=[];score_details=[];group_details=[]
 def check(label,ok,detail=''):
  checks.append(dict(check=label,pass_check=bool(ok),detail=detail))
  if not ok:raise AssertionError(label+': '+str(detail))
 counts={s:pq.ParquetFile(root/f'02_DROUGHT_EVENTS/CORRECTED_EVENT_LEVEL_R2_{s}.parquet').metadata.num_rows for s in SCALES}
 check('frozen scale-event row counts',counts==dict(D1=90971,D3=101957,D6=87221),str(counts));check('inventory total',sum(counts.values())==280149)
 domain=pq.read_table(root/'01_DOMAIN/GLOBAL_FOREST_ELIGIBILITY.parquet',columns=['forest_mask_30']).column(0).to_pylist()
 check('forest-cover-eligible domain',sum(v==1 for v in domain)==16616)
 pkeys={};timing=[]
 for s in SCALES:
  pf=root/f'03_RECOVERY_P1_P2/RECOVERY_PERSISTENCE_EVENT_LEVEL_{s}.parquet'
  cols=['event_id','p1_r2_recovery_month','p1_r2_confirmation_month','p2_r2_recovery_month','p2_r2_confirmation_month']
  rr=pq.read_table(pf,columns=cols).to_pylist();pkeys[s]={r['event_id'] for r in rr};check(s+' persistence unique keys',len(rr)==len(pkeys[s])==counts[s])
  for r in rr:
   for rule,delta in [('p1',0),('p2',1)]:
    a,b=r[rule+'_r2_recovery_month'],r[rule+'_r2_confirmation_month']
    if a:check(rule+' assigned/confirmed month '+r['event_id'],bool(b) and month(b)-month(a)==delta)
  timing.append(dict(scale=s,rows=len(rr),P1_confirmation_offset_months=0,P2_confirmation_offset_months=1))
 # Confirm identities only: never unpickle frozen model weights in this audit.
 for s,expected in EXPECTED_MODELS.items():
  h=hashlib.sha256((U/f'frozen_models/CORRECTED_MODEL_{s}_HAZARD.pkl').read_bytes()).hexdigest();check(s+' frozen model SHA',h==expected)
 per_scale={};comparison=csvrows(U/'S5_Hminus1/S5_Horizon_Comparison.csv')
 for s in SCALES:
  rows=csvrows(U/f'S5_Hminus1/S5_Event_Scores_READONLY_DERIVED_{s}.csv');z=np.load(U/f'S5_Hminus1/monthly_hazard/S5_FROZEN_P1_MONTHLY_HAZARD_{s}.npz',allow_pickle=False)
  ids=z['event_id'];hs=z['H'];off=z['offset'];q=z['q_recovery_hazard'];check(s+' NPZ keyed alignment',len(rows)==len(ids) and len(off)==len(rows)+1)
  check(s+' NPZ model identity',str(z['model_sha256'])==EXPECTED_MODELS[s]);valid=[];maximum=0
  for i,r in enumerate(rows):
   check(s+' event-key alignment '+str(i),r['event_id']==str(ids[i]) and r['event_id'] in pkeys[s] and int(r['H'])==int(hs[i]))
   h=int(hs[i]);a,b,flag=score_lengths(h);check(s+' stored length '+str(i),int(r['L_H'])==a and int(r['L_before'])==b and r['cap_status']==flag)
   if r['status']!='VALID':check(s+' invalid row not imputed '+str(i),off[i]==off[i+1] and not math.isfinite(number(r['strict_before_score'])));continue
   pa,pb,fl=frozen_scores(q[off[i]:off[i+1]],h)
   err=max(abs(pa-number(r['original_H_score'])),abs(pa-number(r['reproduced_H_score'])),abs(pb-number(r['strict_before_score'])));maximum=max(maximum,err)
   check(s+' H / Hminus1 tolerance '+str(i),err<=TOL);valid.append(r)
  per_scale[s]=rows
  ref=next(r for r in comparison if r['scale']==s and r['group_dimension']=='GLOBAL' and r['stratum']=='ALL_ORIGINAL_COHORT')
  ah=auc([int(r['outcome']) for r in valid],[number(r['original_H_score']) for r in valid]);ab=auc([int(r['outcome']) for r in valid],[number(r['strict_before_score']) for r in valid])
  check(s+' frozen global AUC',same(ah,ref['AUC_H']) and same(ab,ref['AUC_H_minus1']))
  score_details.append(dict(scale=s,N_ER=len(rows),N_AUC=len(valid),invalid=len(rows)-len(valid),positive=sum(int(r['outcome']) for r in valid),negative=sum(1-int(r['outcome']) for r in valid),AUC_H=ah,AUC_Hminus1=ab,max_score_absolute_error=maximum))
 groups=csvrows(U/'S5_Hminus1/S5_Category_Change.csv');check('19 numeric groups + historical pilot',len(groups)==20 and sum(r['group_dimension']!='pilot_constraint' for r in groups)==19)
 source_groups=csvrows(U/'SourceData/SourceData_FigS4_Stage2D.csv')
 for r in groups:
  dim,g=r['group_dimension'],r['group'];src=next(x for x in source_groups if x['group_dimension']==dim and x['group']==g)
  if dim=='pilot_constraint':
   check('Amazon pilot retains nonnumeric limitation',r['before_diagnostic_grade']=='LIMITED' and not math.isfinite(number(r['AUC_H_minus1_median'])) and src['role']=='historical pilot');continue
  field={'forest_type':'forest_type_group','climate_zone':'climate_zone_group','large_region':'large_region_group'}[dim];values=[];ner=nauc=0
  for s in SCALES:
   subset=[x for x in per_scale[s] if x[field]==g];v=[x for x in subset if x['status']=='VALID'];ner+=len(subset);nauc+=len(v);values.append(auc([int(x['outcome']) for x in v],[number(x['strict_before_score']) for x in v]))
  med=median_finite(values);gr=grade(ner,number(r['original_ER']),number(r['original_CI_low']),med)
  check('group N/AUC/status '+dim+':'+g,ner==int(r['original_N_ER']) and nauc==int(r['N_AUC']) and same(med,r['AUC_H_minus1_median']) and gr==r['before_diagnostic_grade']==r['original_grade'])
  check('current S4 Source Data '+dim+':'+g,same(src['conditional_strict_before_event_AUC'],med) and src['evidence_status']==gr and int(src['N_ER'])==ner and int(src['N_AUC'])==nauc)
  group_details.append(dict(dimension=dim,group=g,N_ER=ner,N_AUC=nauc,strict_before_median_scale_AUC=None if math.isnan(med) else med,evidence_status=gr))
 # Reconstruct Table S1 counts using the accepted keyed, derived diagnostic table.
 expected=csvrows(U/'SourceData/Supplementary_Table_S1.csv');table_details=[]
 for s in SCALES:
  rr=csvrows(U/f'B2_Response/B2_Recovery_Status_READONLY_DERIVED_{s}.csv')
  for rule in ['P1','P2']:
   sub=[r for r in rr if r['rule']==rule];check(s+rule+' status key set',len(sub)==counts[s] and {r['event_id'] for r in sub}==pkeys[s])
   end=[r for r in sub if math.isfinite(number(r['end_anomaly']))];above=[r for r in sub if number(r['end_anomaly'])>-.5];one=[r for r in sub if int(r['right_censored'])==0 and number(r['duration'])==1];both=[r for r in one if number(r['end_anomaly'])>-.5]
   actual={'N_all':len(sub),'N_end_finite':len(end),'N_end_missing':len(sub)-len(end),'N_end_above':len(above),'N_R2_duration1':len(one),'N_end_above_AND_duration1':len(both),'N_duration1_end_missing':sum(not math.isfinite(number(r['end_anomaly'])) for r in one),'N_true_confirmation_month1':sum(number(r['confirmation_elapsed'])==1 and int(r['right_censored'])==0 for r in sub),'N_complete':sum(int(r['right_censored'])==0 for r in sub),'N_right_censored':sum(int(r['right_censored'])==1 for r in sub)}
   target=next(r for r in expected if r['scale']==s and r['rule']==rule)
   for k,v in actual.items():check('TableS1 '+s+rule+' '+k,v==int(target[k]))
   for k,n,d in [('end_above_among_all',len(above),len(sub)),('end_above_among_finite',len(above),len(end)),('duration1_given_end_above',len(both),len(above)),('end_above_given_duration1',len(both),len(one))]:check('TableS1 ratio '+s+rule+' '+k,same(n/d,target[k]))
   table_details.append(dict(scale=s,rule=rule,**actual))
  for r in csvrows(U/f'B2_Response/B2_Event_Response_Check_{s}.csv'):
   check('B2 existing within-drought response check '+r['event_id'],r['gate']=='VERIFIED' and number(r['within_drought_minimum_sd'])<-.5 and same(number(r['loss_field_sd']),-number(r['within_drought_minimum_sd'])))
 # Synthetic boundary QA is not an additional scientific analysis.
 for h,length in [(1,0),(2,1),(240,239),(241,240),(242,240),(300,240)]:check('synthetic Hminus1 length '+str(h),score_lengths(h)[1]==length)
 check('synthetic empty product',frozen_scores([.2],1)[1]==1);check('synthetic last hazard1 avoids division',same(frozen_scores([.2,1],2)[1],.8))
 return dict(status='PASS_FROZEN_ARTIFACT_REPRODUCTION',checks=len(checks),failures=[],tolerance=TOL,model_loaded=False,predictions=False,fits=False,bootstrap=False,raw_arrays_read=False,event_identification=False,P2_timing=timing,S5=score_details,numeric_groups=group_details,TableS1=table_details,environment=dict(python=platform.python_version(),numpy=np.__version__,pyarrow=__import__('pyarrow').__version__),scope='Numerical reproduction from frozen stored monthly probabilities and keyed derived diagnostic fields; original raw-array audit and fresh model inference not rerun')
def main():
 p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--report',type=Path,required=True);args=p.parse_args();root=args.data_root.resolve();report=args.report.resolve()
 if report.is_relative_to(root):raise ValueError('Report must be outside the input archive')
 result=verify(root);report.parent.mkdir(parents=True,exist_ok=True);report.write_text(json.dumps(result,ensure_ascii=False,indent=2,allow_nan=False),encoding='utf-8');print(json.dumps(dict(status=result['status'],checks=result['checks'],S5=result['S5'],numeric_groups=len(result['numeric_groups']),TableS1_rows=len(result['TableS1'])),ensure_ascii=False,indent=2))
if __name__=='__main__':main()
