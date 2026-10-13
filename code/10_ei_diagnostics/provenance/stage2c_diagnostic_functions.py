"""PROVENANCE_ONLY original accepted diagnostic function bodies.

These functions require the original globals, workspace, trusted model inputs,
original runtime and arrays. They are not a standalone runnable pipeline.
No module-level computation, model load, inference, training or file creation.
The supported runnable archive verifier is ../verify_ei_archive.py.
"""
from __future__ import annotations
def log(s):
 line=time.strftime('%Y-%m-%d %H:%M:%S')+' '+s
 print(line,flush=True)
 with (O/'EXECUTION_LOG.txt').open('a',encoding='utf-8') as f:f.write(line+'\n')

def sha(p):
 h=hashlib.sha256()
 with p.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()

def jout(p,obj):p.write_text(json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=True),encoding='utf-8')

def cout(p,rows,fields=None):
 with p.open('w',encoding='utf-8-sig',newline='') as f:
  w=csv.DictWriter(f,fieldnames=fields or list(rows[0]));w.writeheader();w.writerows(rows)

def readcsv(p):
 with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def finite(v):
 try:x=float(v)
 except (TypeError,ValueError):return math.nan
 return x if math.isfinite(x) else math.nan

def mi(s):
 y,m=map(int,s.split('-'));assert 1<=m<=12;return (y-2001)*12+m-1

def eq(a,b):
 x,y=finite(a),finite(b)
 return (math.isnan(x) and math.isnan(y)) or x==y

class StopDiagnostic(Exception):pass

def require(cond,msg):
 if not cond:raise StopDiagnostic(msg)

class PrimitiveUnpickler(pickle.Unpickler):
 def find_class(self,module,name):raise StopDiagnostic('Executable object in frozen event file: '+module+'.'+name)

def events(p):
 with p.open('rb') as f:data=PrimitiveUnpickler(f).load()
 require(isinstance(data,list) and all(isinstance(r,dict) for r in data),'Unexpected event representation '+str(p));return data

def checkkeys(rows,s):
 seen=set()
 for r in rows:
  key=r.get('event_id');require(isinstance(key,str) and key and key not in seen,'Missing/duplicate event key '+str(key));seen.add(key)
  require(r.get('spei_timescale')==s,'Scale/key mismatch '+key)
  parts=key.split('_');require(len(parts)==4 and parts[0]==s and parts[1]==str(r['pixel_id']) and parts[2]==r['event_start'].replace('-','') and parts[3].isdigit(),'Event-ID components conflict '+key)
  start,end=mi(r['event_start']),mi(r['event_end']);require(0<=start<=end<288,'Invalid event month '+key)
  h=finite(r.get('next_drought_interval_months'))
  if math.isfinite(h):require(h>=1 and h==round(h) and end+int(h)<288,'Invalid frozen next-drought interval '+key)
 return seen

def source_functions(p,names,env):
 t=ast.parse(p.read_text(encoding='utf-8-sig'));nodes=[n for n in t.body if isinstance(n,ast.FunctionDef) and n.name in names]
 require({n.name for n in nodes}==set(names),'Source helper missing')
 exec(compile(ast.Module(body=nodes,type_ignores=[]),str(p),'exec'),env)
 return {n:env[n] for n in names}

def nofit(*args,**kwargs):raise StopDiagnostic('Training forbidden in this diagnostic')

def initialize():
 require(not (O/'PROTOCOL_LOCK.json').exists(),'Run already initialized; do not overwrite diagnostic results')
 protocol=dict(authorization='User Stage2C second batch A1+B2',H_length='min(H,240)',before_length='min(max(H-1,0),240)',H1_empty_product=1,H_gt_241='CAP_TRUNCATED',reproduction_abs_tolerance=TOL,same_cohort_labels_groups_thresholds=True,training=False,bootstrap=False,word_and_figures_edited=False,loss_field_array_tolerance=TOL,threshold_sd=THRESHOLD,invalid_probability='Paired exclusion; never clip',duplicates='Stop affected calculation',new_events=False)
 jout(O/'PROTOCOL_LOCK.json',protocol)
 versions=dict(python=platform.python_version(),numpy=np.__version__,scipy=scipy.__version__,sklearn=sklearn.__version__,platform=platform.platform())
 jout(E/'RUNTIME.json',versions)
 require(versions['python']=='3.11.9' and versions['numpy']=='2.4.6' and versions['scipy']=='1.17.1' and versions['sklearn']=='1.9.0','Frozen analysis environment mismatch')
 selected=list(B.glob('*.docx'))+list(B.glob('0*.md'))+[C/'task0010c_models.py',C/'task0010c_consensus.py',C/'task0010c_dryrun.py',C/'task0010c_core.py',C/'CORRECTED_MODEL_FREEZE_RECORD.csv',C/'CORRECTED_APPLICATION_EVIDENCE_STATUS.csv',C/'CORRECTED_PIXEL_MULTISCALE_PRIORITY.csv',P/'task0010e_persistence.py',P/'RECOVERY_PERSISTENCE_BY_SCALE.csv']
 selected += [C/f'CORRECTED_MODEL_{s}_HAZARD.pkl' for s in SCALES]+[C/f'_working/events_modeled_{s}.pkl' for s in SCALES]+[P/f'_working/persistence_{s}.pkl' for s in SCALES]
 selected += [A/'_processing_cache'/n for n in ['global_kndvi_anomaly.npy','forest_rows.npy','forest_cols.npy']]
 before=[]
 for p in selected:
  q=p.stat();before.append(dict(path=str(p),bytes=q.st_size,mtime_ns=q.st_mtime_ns,sha256=sha(p)))
 jout(E/'INPUT_SHA256_BEFORE.json',before);log('Input fingerprints frozen: '+str(len(before)))

def models():
 ms={};ident=[];freeze={r['spei_timescale']:r for r in readcsv(C/'CORRECTED_MODEL_FREEZE_RECORD.csv')}
 for s in SCALES:
  p=C/f'CORRECTED_MODEL_{s}_HAZARD.pkl';require(sha(p)==EXPECTED[s],'Model SHA mismatch '+s)
  with warnings.catch_warnings(record=True) as caught:
   with p.open('rb') as f:payload=pickle.load(f)
  require(not caught,'Model deserialization warning '+s+': '+str(caught))
  require(payload['numeric_features']==FEATURES and payload['categorical_features']==['forest_type','climate_zone'] and payload['time_features']==['month_since_drought_end','log1p_month_since_drought_end'] and payload['definition']=='R2','Frozen model feature metadata conflict '+s)
  require(freeze[s]['prospective_numeric_features'].split('|')==FEATURES,'Freeze record feature sequence conflict '+s)
  m=payload['model'];require(type(m) is Pipeline,'Model not Pipeline '+s)
  require([type(v).__name__ for n,v in m.steps]==['StandardScaler','LogisticRegression'],'Pipeline class sequence mismatch '+s)
  sc,lr=m.steps[0][1],m.steps[1][1]
  require(sc.n_features_in_==lr.n_features_in_==29 and np.array_equal(lr.classes_,[0,1]),'Model columns/classes mismatch '+s)
  require(np.isfinite(lr.coef_).all() and np.isfinite(sc.mean_).all() and np.isfinite(sc.scale_).all(),'Invalid fitted model numbers '+s)
  pars=lr.get_params();require(pars['C']==1 and pars['max_iter']==1000 and pars['random_state']==9021009 and pars['class_weight'] is None and pars['solver']=='lbfgs' and pars['fit_intercept'],'Hazard parameter identity mismatch '+s)
  require(sc.with_mean and sc.with_std,'Scaler semantics mismatch '+s)
  ms[s]=m;ident.append(dict(scale=s,path=str(p),sha256=EXPECTED[s],steps=[(n,type(v).__name__) for n,v in m.steps],columns=29,numeric_features=FEATURES,categorical_encoding='1-5 indicators each; missing/other all zero before saved scaling',time_features=payload['time_features'],classes=lr.classes_.tolist(),class_1='recovery hazard: original hazard_data sets final recovery month to1',logistic_parameters=pars,model_identity='VERIFIED',version=sklearn.__version__))
 jout(E/'MODEL_PIPELINE_IDENTITY.json',ident);log('All 3 P1 models: SHA, Pipeline, classes and29 columns verified')
 return ms

class Capture:
 def __init__(self,model):self.model=model;self.probabilities=[]
 def predict_proba(self,X):
  p=self.model.predict_proba(X);self.probabilities.append(p[:,1].copy());return p

def reproduce(ms,pixels):
 gates=[]
 for s in SCALES:
  raw=events(C/f'_working/events_modeled_{s}.pkl');checkkeys(raw,s)
  cohort=HOLD(raw,pixels,s,'consensus_ge2_risk');byid={r['event_id']:r for r in raw};selected=[byid[r['event_id']] for r in cohort]
  require(all(int(r['outcome']) in [0,1] and float(r['outcome'])==int(r['outcome']) for r in cohort),'Nonbinary S5 label '+s)
  X,_=FUN['matrix'](selected,FEATURES)
  eligible=[i for i,r in enumerate(selected) if math.isfinite(finite(r.get('next_drought_interval_months'))) and finite(r['next_drought_interval_months'])>=1 and np.isfinite(X[i]).all()]
  capture=Capture(ms[s]);pred=FUN['event_incomplete_probability'](capture,selected,FEATURES)
  require(len(capture.probabilities)==len(eligible),'Monthly capture alignment conflict '+s)
  qi={i:q for i,q in zip(eligible,capture.probabilities)};audit=[];flat=[];offset=[0];maxerr=0.
  for i,(r,c,score) in enumerate(zip(selected,cohort,pred)):
   old=finite(c['prediction']);h=int(round(finite(r['next_drought_interval_months'])));q=qi.get(i,np.array([],float))
   require(not len(q) or np.isfinite(q).all() and np.all((q>=0)&(q<=1)),'Invalid monthly probability '+s+' '+r['event_id'])
   require(math.isfinite(old)==math.isfinite(score),'Frozen prediction validity mismatch '+s+' '+r['event_id'])
   err=abs(old-score) if math.isfinite(old) else math.nan
   if math.isfinite(err):maxerr=max(maxerr,err)
   row=dict(scale=s,event_id=r['event_id'],pixel_id=r['pixel_id'],event_start=r['event_start'],event_end=r['event_end'],outcome=int(c['outcome']),flag=c['flag'],forest_type_group=c['forest_type_group'],climate_zone_group=c['climate_zone_group'],large_region_group=c['large_region_group'],spatial_block_id=c['spatial_block_id'],H=h,L_H=min(h,240),original_H_score=old,reproduced_H_score=float(score),abs_error=err,status='VALID' if math.isfinite(score) else 'INVALID_NUMERIC_FEATURES',model_sha256=EXPECTED[s])
   audit.append(row);flat.extend(q);offset.append(len(flat))
   if math.isfinite(err) and err>TOL:
    cout(O/f'S5_H_Reproduction_Audit_{s}.csv',audit);raise StopDiagnostic(f'Original H reproduction failed {s} {r["event_id"]}: error={err:.17g}')
  cout(O/f'S5_H_Reproduction_Audit_{s}.csv',audit)
  np.savez_compressed(W/f'hazards_{s}.npz',q=np.asarray(flat),offset=np.asarray(offset,dtype=np.int64))
  nvalid=sum(r['status']=='VALID' for r in audit)
  gates.append(dict(scale=s,N_ER=len(cohort),N_valid_H=nvalid,N_invalid=len(cohort)-nvalid,max_abs_error=maxerr,tolerance=TOL,pass_gate=True))
  log(f'{s} original H PASS: N_ER={len(cohort)}, valid={nvalid}, max_abs_error={maxerr:.3g}')
  del raw,byid,selected,X,capture,flat,qi
 cout(O/'S5_H_Reproduction_Gate.csv',gates);jout(E/'ALL_H_GATES.json',gates)

def aucs(rows):
 valid=[r for r in rows if r['status']=='VALID'];y=np.asarray([int(r['outcome']) for r in valid]);p=np.asarray([float(r['reproduced_H_score']) for r in valid]);b=np.asarray([float(r['strict_before_score']) for r in valid])
 reason='VALID' if len(y)>=20 and len(np.unique(y))==2 else 'INSUFFICIENT_N_OR_SINGLE_CLASS'
 ah=float(roc_auc_score(y,p)) if reason=='VALID' else math.nan;ab=float(roc_auc_score(y,b)) if reason=='VALID' else math.nan
 return dict(N_ER=len(rows),N_AUC=len(valid),N_positive_ER=sum(int(r['outcome']) for r in rows),N_negative_ER=sum(1-int(r['outcome']) for r in rows),N_positive_AUC=int(y.sum()),N_negative_AUC=int(len(y)-y.sum()),N_invalid=len(rows)-len(valid),H1_count=sum(int(r['H'])==1 for r in rows),H241_count=sum(int(r['H'])==241 for r in rows),CAP_TRUNCATED_count=sum(int(r['H'])>241 for r in rows),H_le240_count=sum(int(r['H'])<=240 for r in rows),N_zero_H_score=sum(float(r['reproduced_H_score'])==0 for r in valid),N_zero_before_score=sum(float(r['strict_before_score'])==0 for r in valid),AUC_H=ah,AUC_H_minus1=ab,delta_AUC=ab-ah,auc_status=reason)

def median(values):
 a=[x for x in values if math.isfinite(x)];return float(np.median(a)) if a else math.nan

def grade(n,er,lo,a):
 return 'SUPPORTED' if n>=300 and math.isfinite(lo) and lo>1 and math.isfinite(a) and a>=.6 else 'CONDITIONAL' if n>=100 and ((math.isfinite(er) and er>1) or (math.isfinite(a) and a>=.6)) else 'LIMITED'

def compare():
 require(all(r['pass_gate'] for r in json.loads((E/'ALL_H_GATES.json').read_text())),'Original H gate not passed')
 old=readcsv(C/'CORRECTED_APPLICATION_EVIDENCE_STATUS.csv');spec=[(r['group_dimension'],r['group']) for r in old if r['group_dimension']!='pilot_constraint'];require(len(spec)==19,'Frozen numeric groups not19')
 comparisons=[];distributions=[];categories=[];allrows={}
 for s in SCALES:
  rows=readcsv(O/f'S5_H_Reproduction_Audit_{s}.csv');store=np.load(W/f'hazards_{s}.npz',allow_pickle=False);q=store['q'];off=store['offset'];require(len(off)==len(rows)+1,'Monthly buffer key mismatch')
  for i,r in enumerate(rows):
   h=int(r['H']);L=min(max(h-1,0),240);p=q[off[i]:off[i+1]]
   r['L_before']=L;r['cap_status']='CAP_TRUNCATED' if h>241 else 'CAP_BOUNDARY_241' if h==241 else 'UNCAPPED';r['strict_before_score']=float(np.prod(1-p[:L])) if r['status']=='VALID' else math.nan
   if r['status']=='VALID':require(len(p)==int(r['L_H']) and r['strict_before_score']+TOL>=float(r['reproduced_H_score']),'Score length/monotonicity conflict '+r['event_id'])
   r['diagnostic_status']='DIAGNOSTIC_ONLY_NOT_SUBMISSION_RESULTS'
  cout(O/f'S5_Event_Scores_READONLY_DERIVED_{s}.csv',rows);allrows[s]=rows
  for dim,group in [('GLOBAL','GLOBAL')]+spec:
   field={'forest_type':'forest_type_group','climate_zone':'climate_zone_group','large_region':'large_region_group'}.get(dim)
   subset=rows if dim=='GLOBAL' else [r for r in rows if r[field]==group]
   for stratum in ['ALL_ORIGINAL_COHORT','H_LE240','H_EQ241','H_GT241_CAP_TRUNCATED']:
    ss=subset if stratum=='ALL_ORIGINAL_COHORT' else [r for r in subset if int(r['H'])<=240] if stratum=='H_LE240' else [r for r in subset if int(r['H'])==241] if stratum=='H_EQ241' else [r for r in subset if int(r['H'])>241]
    comparisons.append(dict(scale=s,group_dimension=dim,group=group,stratum=stratum,**aucs(ss),diagnostic_status='DIAGNOSTIC_ONLY_NOT_SUBMISSION_RESULTS'))
  valid=[r for r in rows if r['status']=='VALID']
  for field in ['original_H_score','strict_before_score']:
   v=np.asarray([float(r[field]) for r in valid]);distributions.append(dict(scale=s,field=field,N=len(v),minimum=float(np.min(v)),q05=float(np.quantile(v,.05)),median=float(np.median(v)),q95=float(np.quantile(v,.95)),maximum=float(np.max(v)),mean=float(np.mean(v))))
 for r in old:
  dim,g=r['group_dimension'],r['group']
  if dim=='pilot_constraint':
   categories.append(dict(group_dimension=dim,group=g,original_N_ER=r['sample_events_total'],N_AUC='NOT_APPLICABLE',original_ER=r['equal_scale_median_enrichment_ratio'],original_CI_low=r['er_5deg_bootstrap_ci_low'],original_CI_high=r['er_5deg_bootstrap_ci_high'],original_median_AUC=r['equal_scale_median_prospective_hazard_auc'],AUC_H_median=math.nan,AUC_H_minus1_median=math.nan,delta_median_AUC=math.nan,original_grade=r['application_evidence_status'],H_reproduced_grade=r['application_evidence_status'],before_diagnostic_grade=r['application_evidence_status'],grade_changed=False,change_reason='Historical pilot constraint retained; no numeric AUC inferred',N_positive_AUC=0,N_negative_AUC=0,N_invalid='NOT_APPLICABLE',CAP_TRUNCATED_count='NOT_APPLICABLE',H1_count='NOT_APPLICABLE',scale_AUC_H='NOT_APPLICABLE',scale_AUC_before='NOT_APPLICABLE',ER_CI_N_changed=False));continue
  comp=[next(c for c in comparisons if c['scale']==s and c['group_dimension']==dim and c['group']==g and c['stratum']=='ALL_ORIGINAL_COHORT') for s in SCALES]
  n=sum(c['N_ER'] for c in comp);ah=median([c['AUC_H'] for c in comp]);ab=median([c['AUC_H_minus1'] for c in comp]);oldauc=finite(r['equal_scale_median_prospective_hazard_auc'])
  require(n==int(r['sample_events_total']) and all(c['N_ER']==int(r[s+'_events']) for c,s in zip(comp,SCALES)),'Frozen group N mismatch '+dim+' '+g)
  require(eq(ah,oldauc) or math.isfinite(ah) and math.isfinite(oldauc) and abs(ah-oldauc)<=TOL,'Original group AUC mismatch '+g)
  er,lo=finite(r['equal_scale_median_enrichment_ratio']),finite(r['er_5deg_bootstrap_ci_low']);gh=grade(n,er,lo,ah);gb=grade(n,er,lo,ab)
  require(gh==r['application_evidence_status'],'Original group grade mismatch '+g)
  categories.append(dict(group_dimension=dim,group=g,original_N_ER=r['sample_events_total'],N_AUC=sum(c['N_AUC'] for c in comp),original_ER=r['equal_scale_median_enrichment_ratio'],original_CI_low=r['er_5deg_bootstrap_ci_low'],original_CI_high=r['er_5deg_bootstrap_ci_high'],original_median_AUC=r['equal_scale_median_prospective_hazard_auc'],AUC_H_median=ah,AUC_H_minus1_median=ab,delta_median_AUC=ab-ah,original_grade=gh,H_reproduced_grade=gh,before_diagnostic_grade=gb,grade_changed=gh!=gb,change_reason='Same grade under frozen thresholds' if gh==gb else 'Only median AUC boundary changed; ER CI N and threshold unchanged',N_positive_AUC=sum(c['N_positive_AUC'] for c in comp),N_negative_AUC=sum(c['N_negative_AUC'] for c in comp),N_invalid=sum(c['N_invalid'] for c in comp),CAP_TRUNCATED_count=sum(c['CAP_TRUNCATED_count'] for c in comp),H1_count=sum(c['H1_count'] for c in comp),scale_AUC_H='|'.join(str(c['AUC_H']) for c in comp),scale_AUC_before='|'.join(str(c['AUC_H_minus1']) for c in comp),ER_CI_N_changed=False))
 cout(O/'S5_Horizon_Comparison.csv',comparisons);cout(O/'S5_Category_Change.csv',categories);cout(O/'S5_Score_Distribution.csv',distributions)
 # Audit any downstream grade effect without making a map or editing source pixels.
 lookup={(r['group_dimension'],r['group']):r for r in categories};pixelrows=readcsv(C/'CORRECTED_PIXEL_MULTISCALE_PRIORITY.csv');changes=[]
 for p in pixelrows:
  oldgrades=[];newgrades=[]
  for dim,field in [('forest_type','forest_type_label'),('climate_zone','climate_zone_label'),('large_region','large_region')]:
   r=lookup.get((dim,p[field]));oldgrades.append(r['original_grade'] if r else 'LIMITED');newgrades.append(r['before_diagnostic_grade'] if r else 'LIMITED')
  amazon=-75<=float(p['longitude'])<=-50 and -15<=float(p['latitude'])<=5
  if amazon:oldgrades.append('LIMITED');newgrades.append('LIMITED')
  rank={'LIMITED':1,'CONDITIONAL':2,'SUPPORTED':3};a=min(oldgrades,key=rank.get);b=min(newgrades,key=rank.get)
  require(a==p['corrected_application_evidence_status'],'Original pixel grade conflict '+p['pixel_id'])
  changes.append(dict(pixel_id=p['pixel_id'],original_grade=a,before_diagnostic_grade=b,changed=a!=b,amazon_constraint=amazon,diagnostic_only=True))
 cout(O/'S5_Downstream_Pixel_Grade_Impact.csv',changes)
 jout(E/'S5_SUMMARY.json',dict(categories_changed=sum(r['grade_changed'] for r in categories),numeric_groups=19,pilot_rows=1,pixel_grade_changes=sum(r['changed'] for r in changes),global_comparisons=[r for r in comparisons if r['group_dimension']=='GLOBAL' and r['stratum']=='ALL_ORIGINAL_COHORT'],grade_counts_before={g:sum(r['original_grade']==g for r in categories) for g in ['SUPPORTED','CONDITIONAL','LIMITED']},grade_counts_after={g:sum(r['before_diagnostic_grade']==g for r in categories) for g in ['SUPPORTED','CONDITIONAL','LIMITED']}))
 log('S5 comparison complete; group grade changes='+str(sum(r['grade_changed'] for r in categories)))

def bstats(scale,rule,cohort,rows):
 n=len(rows);complete=[r for r in rows if r['right_censored']==0];v=np.array([r['duration'] for r in complete],float)
 def ratio(a,b):return a/b if b else math.nan
 nc=sum(r['field_gate']=='NO_THRESHOLD_RESPONSE' for r in rows);nm=sum(r['field_gate']=='MISSING_LOSS' for r in rows);nnone=sum(math.isfinite(r['loss']) and r['loss']<=0 for r in rows)
 return dict(scale=scale,persistence_rule=rule,cohort=cohort,N_all=n,N_loss_finite=n-nm,N_loss_missing=nm,N_no_threshold_response=nc,proportion_no_threshold_response_all=ratio(nc,n),N_no_any_negative_response=nnone,proportion_no_any_negative_all=ratio(nnone,n),N_complete=len(complete),N_right_censored=n-len(complete),right_censor_fraction=ratio(n-len(complete),n),N_assigned_duration1=sum(r['duration']==1 for r in complete),assigned_duration1_among_complete=ratio(sum(r['duration']==1 for r in complete),len(complete)),N_confirmation_at_month1=sum(r['confirmation_elapsed']==1 for r in complete),median_complete_duration=float(np.median(v)) if len(v) else math.nan,p95_complete_duration=float(np.quantile(v,.95)) if len(v) else math.nan,N_complete_gt3=int(np.sum(v>3)),N_complete_gt6=int(np.sum(v>6)),N_complete_gt12=int(np.sum(v>12)),observation_endpoint='2023-12 administrative confirmation cutoff' if cohort=='TEMPORAL_ADMIN_2023' else 'Frozen full record through2024',units='scale-event records; not independent physical droughts')

def response_fields():
 # Complete all B1 field validation and statistics before opening the array in B2.
 summaries=[];subsets=[];gates=[]
 archived={r['spei_timescale']:r for r in readcsv(P/'RECOVERY_PERSISTENCE_BY_SCALE.csv') if r['recovery_definition']=='R2'}
 for s in SCALES:
  raw=events(C/f'_working/events_modeled_{s}.pkl');pr=events(P/f'_working/persistence_{s}.pkl');require(checkkeys(raw,s)==checkkeys(pr,s),'B1 event key-set mismatch '+s);byid={r['event_id']:r for r in pr};processed=[]
  for r in raw:
   p=byid[r['event_id']];key=r['event_id']
   for f in ['pixel_id','event_start','event_end','spatial_block_id','forest_type','climate_zone']:require(r[f]==p[f],'B1 metadata conflict '+key+' '+f)
   for f in FEATURES:require(eq(r[f],p[f]),'B1 numeric-field conflict '+key+' '+f)
   require(eq(r['kNDVI_loss_amplitude'],r['kNDVI_loss_amplitude_sd']),'B1 loss alias conflict '+key)
   loss=finite(r['kNDVI_loss_amplitude_sd']);require(math.isfinite(loss) and loss>.5,'B1 frozen damage-gate field conflict '+key)
   for suf,f in [('right_censored','right_censored'),('recovery_time_from_drought_end_months','recovery_time_from_drought_end_months'),('recovery_month','r2_recovery_month'),('minimum_month','r2_minimum_month'),('temporal_evaluation_right_censored','temporal_evaluation_right_censored')]:
    a,b=r[f],p['p1_r2_'+suf];require(a==b if isinstance(a,str) else eq(a,b),'B1 P1 stored-field conflict '+key+' '+suf)
   start,end=mi(r['event_start']),mi(r['event_end'])
   for rule,k in [('P1','p1_r2'),('P2','p2_r2')]:
    cens=int(p[k+'_right_censored']);dur=finite(p[k+'_recovery_time_from_drought_end_months']);rm=p[k+'_recovery_month'];cm=p[k+'_confirmation_month'];confirm=mi(cm)-end if cm else math.nan
    require(cens in [0,1] and (cens==1 and not math.isfinite(dur) and not rm and not cm or cens==0 and dur>=1 and dur==round(dur) and mi(rm)-end==dur and confirm==dur+(rule=='P2')),'B1 duration/confirmation conflict '+key+' '+rule)
    processed.append(dict(scale=s,rule=rule,event_id=key,event_start=start,loss=loss,field_gate='OBSERVED_THRESHOLD_RESPONSE',right_censored=cens,duration=dur,confirmation_elapsed=confirm,analysis_period=p[k+'_analysis_period'],temporal_eligible=int(p[k+'_temporal_evaluation_eligible']),temporal_censor=int(p[k+'_temporal_evaluation_right_censored']),temporal_duration=finite(p[k+'_temporal_evaluation_recovery_time_from_drought_end_months'])))
  for rule in ['P1','P2']:
   rr=[r for r in processed if r['rule']==rule];require(sum(not r['right_censored'] for r in rr)==int(archived[s][rule+'_complete_count']),'B1 archived complete-count mismatch '+s+' '+rule)
   scopes={'ALL_RECORDS_FULL_FOLLOWUP':rr,'TRAIN_2001_2020':[r for r in rr if r['analysis_period']=='TRAIN_2001_2020'],'TRAIN_BOUNDARY_EXCLUDED':[r for r in rr if r['analysis_period']=='TRAIN_BOUNDARY_EXCLUDED'],'TEMPORAL_2021_2023_FULL_FOLLOWUP':[r for r in rr if r['temporal_eligible']],'CURRENT_2024_FULL_FOLLOWUP':[r for r in rr if r['event_start']>=276]}
   scopes['TEMPORAL_ADMIN_2023']=[dict(r,right_censored=r['temporal_censor'],duration=r['temporal_duration'],confirmation_elapsed=r['temporal_duration']+(rule=='P2') if math.isfinite(r['temporal_duration']) else math.nan) for r in rr if r['temporal_eligible']]
   for name,sub in scopes.items():summaries.append(bstats(s,rule,name,sub))
   for group in ['OBSERVED_THRESHOLD_RESPONSE','NO_THRESHOLD_RESPONSE','MISSING_LOSS']:subsets.append(dict(response_subset=group,**bstats(s,rule,'ALL_RECORDS_FULL_FOLLOWUP',[r for r in rr if r['field_gate']==group])))
  gates.append(dict(scale=s,N_events=len(raw),N_P1_P2_matched=len(pr),N_no_threshold_response=0,N_loss_missing=0,N_key_conflicts=0,status='VERIFIED'))
  log(f'{s} B1 field checks and descriptive statistics PASS: {len(raw)} events')
  del raw,pr,byid,processed
 cout(O/'B1_Drought_Response_and_Duration_Summary.csv',summaries);cout(O/'B1_Response_Subset_Summary.csv',subsets);cout(O/'B1_Field_Gates.csv',gates)
 jout(E/'B1_GATE.json',dict(status='PASS_ALL_SCALES_BEFORE_B2',summary_sha256=sha(O/'B1_Drought_Response_and_Duration_Summary.csv'),subset_sha256=sha(O/'B1_Response_Subset_Summary.csv')))
 log('All B1 gates complete; B2 array access may now begin')

def response():
 require(json.loads((E/'B1_GATE.json').read_text())['status']=='PASS_ALL_SCALES_BEFORE_B2','B1 must finish before B2')
 anomaly=np.load(A/'_processing_cache/global_kndvi_anomaly.npy',mmap_mode='r',allow_pickle=False);fr=np.load(A/'_processing_cache/forest_rows.npy',allow_pickle=False);fc=np.load(A/'_processing_cache/forest_cols.npy',allow_pickle=False)
 require(anomaly.shape==(288,16616) and len(fr)==len(fc)==16616,'Frozen anomaly geometry mismatch')
 lookup={int(r)*720+int(c):i for i,(r,c) in enumerate(zip(fr,fc))};require(len(lookup)==16616,'Duplicate frozen pixel keys')
 summaries=[];contingency=[];associations=[];gates=[];subsetstats=[];checks=[]
 archived={r['spei_timescale']:r for r in readcsv(P/'RECOVERY_PERSISTENCE_BY_SCALE.csv') if r['recovery_definition']=='R2'}
 for s in SCALES:
  raw=events(C/f'_working/events_modeled_{s}.pkl');pr=events(P/f'_working/persistence_{s}.pkl');ks=checkkeys(raw,s);kp=checkkeys(pr,s);require(ks==kp,'P1/P2 event key-set mismatch '+s);byid={r['event_id']:r for r in pr}
  processed=[];event_checks=[];maxerr=0.
  for r in raw:
   p=byid[r['event_id']];key=r['event_id']
   for field in ['pixel_id','event_start','event_end','spatial_block_id','forest_type','climate_zone']:
    require(r[field]==p[field],'P1/P2 metadata conflict '+key+' '+field)
   for field in FEATURES:require(eq(r[field],p[field]),'P1/P2 feature conflict '+key+' '+field)
   for suffix,field in [('right_censored','right_censored'),('recovery_time_from_drought_end_months','recovery_time_from_drought_end_months'),('recovery_month','r2_recovery_month'),('minimum_month','r2_minimum_month'),('temporal_evaluation_right_censored','temporal_evaluation_right_censored')]:
    a,b=r[field],p['p1_r2_'+suffix];require(a==b if isinstance(a,str) else eq(a,b),'P1 stored recovery-field conflict '+key+' '+suffix)
   start,end=mi(r['event_start']),mi(r['event_end']);require(r['pixel_id'] in lookup,'Event pixel absent '+key)
   series=anomaly[start:end+1,lookup[r['pixel_id']]];ok=np.isfinite(series);require(ok.any(),'No finite within-drought anomaly '+key)
   minimum=float(np.nanmin(series));loss=finite(r['kNDVI_loss_amplitude_sd']);err=abs(loss-(-minimum));maxerr=max(maxerr,err)
   require(math.isfinite(loss) and eq(r['kNDVI_loss_amplitude'],loss) and err<=TOL,'Frozen loss/array conflict '+key)
   require(minimum<THRESHOLD and loss>.5,'Frozen event damage-gate conflict '+key)
   minimum_month=start+int(np.nanargmin(series));require(mi(r['r2_minimum_month'])==minimum_month,'Frozen minimum month conflict '+key)
   require(mi(p['p2_r2_minimum_month'])==minimum_month,'P2 minimum month conflict '+key)
   endvalue=float(anomaly[end,lookup[r['pixel_id']]]);endstate='MISSING' if not math.isfinite(endvalue) else 'ABOVE_THRESHOLD' if endvalue>THRESHOLD else 'EQUAL_THRESHOLD' if endvalue==THRESHOLD else 'BELOW_THRESHOLD'
   event_checks.append(dict(scale=s,event_id=key,pixel_id=r['pixel_id'],event_start=r['event_start'],event_end=r['event_end'],loss_field_sd=loss,within_drought_minimum_sd=minimum,loss_abs_error=err,N_drought_calendar_months=len(series),N_drought_finite_months=int(ok.sum()),N_drought_missing_months=int((~ok).sum()),N_drought_below_threshold_months=int(np.sum(ok&(series<THRESHOLD))),end_anomaly_sd=endvalue,end_state=endstate,gate='VERIFIED',P1_P2_keys_and_loss_match=True))
   for rule,k in [('P1','p1_r2'),('P2','p2_r2')]:
    cens=int(p[k+'_right_censored']);dur=finite(p[k+'_recovery_time_from_drought_end_months']);rm=p[k+'_recovery_month'];cm=p[k+'_confirmation_month'];confirm=mi(cm)-end if cm else math.nan
    require(cens in [0,1] and (cens==1 and not math.isfinite(dur) and not rm and not cm or cens==0 and dur>=1 and dur==round(dur) and mi(rm)-end==dur and confirm==dur+(rule=='P2')),'Recovery duration/confirmation conflict '+key+' '+rule)
    processed.append(dict(scale=s,rule=rule,event_id=key,event_start=start,event_end=end,loss=loss,field_gate='OBSERVED_THRESHOLD_RESPONSE' if loss>.5 else 'NO_THRESHOLD_RESPONSE',right_censored=cens,duration=dur,confirmation_elapsed=confirm,end_state=endstate,end_anomaly=endvalue,analysis_period=p[k+'_analysis_period'],temporal_eligible=int(p[k+'_temporal_evaluation_eligible']),temporal_censor=int(p[k+'_temporal_evaluation_right_censored']),temporal_duration=finite(p[k+'_temporal_evaluation_recovery_time_from_drought_end_months']),N_drought_missing=int((~ok).sum())))
  cout(O/f'B2_Event_Response_Check_{s}.csv',event_checks)
  cout(O/f'B2_Recovery_Status_READONLY_DERIVED_{s}.csv',processed)
  gates.append(dict(scale=s,N_events=len(raw),N_P1_P2_matched=len(pr),N_verified_loss_and_array=len(event_checks),max_loss_abs_error=maxerr,N_gate_conflicts=0,N_event_key_conflicts=0,pass_gate=True))
  for rule in ['P1','P2']:
   rr=[r for r in processed if r['rule']==rule]
   actual=sum(r['right_censored']==0 for r in rr);require(actual==int(archived[s][rule+'_complete_count']),'Archived complete-count mismatch '+s+' '+rule)
   require(abs(np.mean([r['right_censored'] for r in rr])-float(archived[s][rule+'_right_censor_rate']))<=TOL,'Archived censor rate mismatch '+s+' '+rule)
   scopes={'ALL_RECORDS_FULL_FOLLOWUP':rr,'TRAIN_2001_2020':[r for r in rr if r['analysis_period']=='TRAIN_2001_2020'],'TRAIN_BOUNDARY_EXCLUDED':[r for r in rr if r['analysis_period']=='TRAIN_BOUNDARY_EXCLUDED'],'TEMPORAL_2021_2023_FULL_FOLLOWUP':[r for r in rr if r['temporal_eligible']],'CURRENT_2024_FULL_FOLLOWUP':[r for r in rr if r['event_start']>=276]}
   scopes['TEMPORAL_ADMIN_2023']=[dict(r,right_censored=r['temporal_censor'],duration=r['temporal_duration'],confirmation_elapsed=r['temporal_duration']+(rule=='P2') if math.isfinite(r['temporal_duration']) else math.nan) for r in rr if r['temporal_eligible']]
   for name,sub in scopes.items():summaries.append(bstats(s,rule,name,sub))
   for group in ['OBSERVED_THRESHOLD_RESPONSE','NO_THRESHOLD_RESPONSE','MISSING_LOSS']:
    sub=[r for r in rr if r['field_gate']==group];subsetstats.append(dict(response_subset=group,**bstats(s,rule,'ALL_RECORDS_FULL_FOLLOWUP',sub)))
   for state in ['ABOVE_THRESHOLD','EQUAL_THRESHOLD','BELOW_THRESHOLD','MISSING']:
    sub=[r for r in rr if r['end_state']==state]
    for outcome in ['ASSIGNED_DURATION1','CONFIRMED_LATER','RIGHT_CENSORED']:
     n=sum((r['right_censored']==1 if outcome=='RIGHT_CENSORED' else r['right_censored']==0 and (r['duration']==1 if outcome=='ASSIGNED_DURATION1' else r['duration']>1)) for r in sub)
     contingency.append(dict(scale=s,rule=rule,end_state=state,recovery_category=outcome,N=n,N_end_state=len(sub),N_all=len(rr),fraction_within_end_state=n/len(sub) if sub else math.nan,description='P2 duration1 is assigned month1, confirmation month2'))
   complete=[r for r in rr if not r['right_censored']];one=[r for r in complete if r['duration']==1];above=[r for r in rr if r['end_state']=='ABOVE_THRESHOLD'];both=[r for r in one if r['end_state']=='ABOVE_THRESHOLD'];finite_end=[r for r in rr if r['end_state']!='MISSING']
   associations.append(dict(scale=s,rule=rule,N_all=len(rr),N_end_finite=len(finite_end),N_end_missing=len(rr)-len(finite_end),N_end_above=len(above),N_R2_duration1=len(one),N_end_above_AND_duration1=len(both),end_above_among_all=len(above)/len(rr),end_above_among_finite=len(above)/len(finite_end) if finite_end else math.nan,duration1_given_end_above=len(both)/len(above) if above else math.nan,end_above_given_duration1=len(both)/len(one) if one else math.nan,N_duration1_end_missing=sum(r['end_state']=='MISSING' for r in one),N_true_confirmation_month1=sum(r['confirmation_elapsed']==1 for r in complete),P2_assignment_note='P2 first qualifying month may have duration1; confirmation is month2',observational_only=True))
  log(f'{s} B2 PASS: {len(raw)} paired events; loss/array max_error={maxerr:.3g}')
  del raw,pr,byid,processed,event_checks
 cout(W/'B1_summary_crosscheck.csv',summaries);cout(W/'B1_subset_crosscheck.csv',subsetstats)
 require(sha(W/'B1_summary_crosscheck.csv')==sha(O/'B1_Drought_Response_and_Duration_Summary.csv') and sha(W/'B1_subset_crosscheck.csv')==sha(O/'B1_Response_Subset_Summary.csv'),'B1/B2 frozen-field summary conflict')
 cout(O/'B2_End_Status_R2_Contingency.csv',contingency);cout(O/'B2_End_Status_R2_Association.csv',associations);cout(O/'B2_Field_Array_Key_Gates.csv',gates)
 jout(E/'B2_SUMMARY.json',dict(gates=gates,end_associations=associations,cohort_definitions='All full-record and temporal administrative endpoints separate; no interpolation; P2 assignment distinct from confirmation',excluded_201646='Archived counter; not interpreted as undamaged events'))

def integrity():
 if not (E/'INPUT_SHA256_BEFORE.json').exists():return
 checks=[]
 for r in json.loads((E/'INPUT_SHA256_BEFORE.json').read_text()):
  p=Path(r['path']);st=p.stat();h=sha(p);checks.append(dict(path=str(p),sha256_before=r['sha256'],sha256_after=h,unchanged=h==r['sha256'] and st.st_size==r['bytes'] and st.st_mtime_ns==r['mtime_ns']))
 cout(E/'INPUT_SHA256_AFTER.csv',checks);require(all(r['unchanged'] for r in checks),'Source input integrity failed')
 log('Source fingerprints unchanged: '+str(len(checks)))
