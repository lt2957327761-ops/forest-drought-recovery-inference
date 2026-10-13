"""Current EI display functions. Frozen tables only; no fitting or resampling.
Plot bodies retain the original Stage2D/Stage2B skeleton. Explicit CLI only.
Input data are never rewritten. Historical S3 display is retained as a frozen PDF.
"""
from pathlib import Path
import csv,json,collections,math,argparse
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import FancyBboxPatch
BLUE='#2166ac';ORANGE='#d97720';INK='#25282c';GRAY='#7b858c'
plt.rcParams.update({'font.family':'Arial','font.size':9,'axes.labelsize':9,'xtick.labelsize':8,'ytick.labelsize':9,'axes.spines.top':False,'axes.spines.right':False,'pdf.fonttype':42,'svg.fonttype':'none','axes.edgecolor':'#686c70','axes.linewidth':.6})
data={};ledger=[];F=None;INPUT_ROOT=None
def rows(book,sheet):
 a=data[book][sheet];h=[str(x).lstrip('\ufeff') for x in a[0]]
 return [dict(zip(h,r)) for r in a[1:]]

def record(fig,panel,row,keys):
 for k in keys:ledger.append(dict(figure=fig,panel=panel,source_field=k,source_value=row[k],display_value=row[k],unchanged=True))

def heading(ax,letter,title):ax.set_title(f'({letter})  {title}',loc='left',pad=12,fontweight='bold',fontsize=10)

def save(fig,name):
 for ext in ['pdf','svg','png']:fig.savefig(F/f'{name}.{ext}',dpi=600,facecolor='white',metadata={'Title':name})
 plt.close(fig)

def stage(ax,xy,wh,text,color):
 ax.add_patch(FancyBboxPatch(xy,*wh,boxstyle='round,pad=0.012,rounding_size=0.02',facecolor=color+'18',edgecolor=color,lw=.9))
 ax.text(xy[0]+wh[0]/2,xy[1]+wh[1]/2,text,ha='center',va='center',fontsize=8,color=INK)

def fig3():
 features=rows('SourceData_Fig3.xlsx','Panel_b_features');rmse=rows('SourceData_Fig3.xlsx','Panel_c_RMSE');haz=rows('SourceData_Fig3.xlsx','Panel_e_hazard')
 fig=plt.figure(figsize=(7.5,7.1));g=fig.add_gridspec(3,2,left=.13,right=.96,bottom=.08,top=.955,height_ratios=[1,1,1.25],hspace=.62,wspace=.5)
 a=fig.add_subplot(g[0,:]);a.set(xlim=(0,1),ylim=(0,1));a.axis('off');heading(a,'a','Information sets in a frozen-background hindcast')
 a.axvspan(0,.24,color=BLUE,alpha=.06);a.axvspan(.24,1,color=ORANGE,alpha=.035)
 a.plot([.24,.24],[.02,.84],color=INK,lw=1,ls='--');a.text(.24,.92,'Drought-end gate',ha='center',fontsize=8,fontweight='bold')
 stage(a,(.015,.47),(.18,.29),'Event-window\ndescriptors',BLUE)
 stage(a,(.315,.5),(.17,.26),'Restricted\nmodel',BLUE);stage(a,(.57,.5),(.36,.26),'Spatial and temporal\nevaluation',BLUE)
 stage(a,(.015,.03),(.18,.26),'Frozen background\nand anomaly baseline',BLUE)
 stage(a,(.315,.03),(.25,.26),'Recovery-period\nclimate and fire',ORANGE)
 stage(a,(.65,.03),(.28,.26),'Retrospective diagnostic\nBase + recovery period',ORANGE)
 for start,end,col in [((.195,.615),(.315,.63),BLUE),((.485,.63),(.57,.63),BLUE),((.195,.16),(.315,.52),BLUE),((.565,.16),(.65,.16),ORANGE)]:a.annotate('',xy=end,xytext=start,arrowprops=dict(arrowstyle='->',lw=1,color=col))
 # Explicitly retain the restricted base in the retrospective feature set.
 a.annotate('',xy=(.78,.31),xytext=(.405,.49),arrowprops=dict(arrowstyle='->',lw=1,color=BLUE,connectionstyle='angle,angleA=-90,angleB=180,rad=4'))
 a.text(.49,.35,'Base features',ha='center',fontsize=7.6,color=BLUE)
 a.text(.96,.015,'No historical-vintage replay',ha='right',va='top',fontsize=7.6,color=GRAY)
 b=fig.add_subplot(g[1,:]);heading(b,'b','Audited roles in the frozen design');b.axis('off')
 counts=collections.Counter(r['role'] for r in features);assert sorted(counts.values())==[1,1,8,19]
 keys=['prospective','retrospective','diagnostic','excluded'];names=['Restricted predictors','Retrospective diagnostics','Outcome horizon','Excluded']
 for i,(k,name) in enumerate(zip(keys,names)):
  y=.9-i*.23;n=counts[k];c=BLUE if n==19 else ORANGE if n==8 else GRAY
  b.text(0,y,name,va='center',fontsize=8.6);b.barh(y,n/50,height=.13,left=.37,color=c);b.text(.38+n/50,y,str(n),va='center',fontsize=9,fontweight='bold')
  ledger.append(dict(figure='Fig3',panel='b',source_field='role_count_'+k,source_value=n,display_value=n,unchanged=True))
 b.set(xlim=(0,1),ylim=(.1,1.04));b.text(.86,.4,'Restricted set\n7 event or history\n12 fixed background',ha='center',va='center',fontsize=8,color=BLUE)
 c=fig.add_subplot(g[2,0]);heading(c,'c','Spatial-block RMSE')
 for i,r in enumerate(rmse):
  y=2-i;p=float(r['prospective_rmse']);q=float(r['retrospective_rmse'])
  c.plot([q,p],[y,y],c='#cfd3d7',lw=3);c.scatter(p,y,c=BLUE,s=34,zorder=3);c.scatter(q,y,c=ORANGE,s=34,marker='s',zorder=3)
  c.text(p+.012,y-.12,f'{p:.3f}',ha='left',va='top',color=BLUE,fontsize=8);c.text(q-.012,y-.12,f'{q:.3f}',ha='right',va='top',color=ORANGE,fontsize=8)
  c.text((p+q)/2,y+.13,'ΔRMSE = '+f"{float(r['delta_retrospective_minus_prospective']):.3f}",ha='center',fontsize=8,color=ORANGE)
  record('Fig3','c',r,['prospective_rmse','retrospective_rmse','delta_retrospective_minus_prospective'])
 c.set(yticks=[2,1,0],yticklabels=['SPEI-1','SPEI-3','SPEI-6'],xlim=(1.04,1.66),ylim=(-.55,2.75),xlabel='RMSE (months)');c.spines['left'].set_visible(False);c.tick_params(axis='y',length=0)
 c.legend(handles=[Line2D([],[],marker='o',color=BLUE,ls='',label='Restricted'),Line2D([],[],marker='s',color=ORANGE,ls='',label='Retrospective')],fontsize=7,loc='upper center',bbox_to_anchor=(.54,1.02),ncol=2,frameon=False,handletextpad=.3,columnspacing=.7)
 d=fig.add_subplot(g[2,1]);heading(d,'d','Monthly-hazard discrimination')
 for i,scale in enumerate(['SPEI-1','SPEI-3','SPEI-6']):
  for rule,col,mark,off in [('P1',BLUE,'o',.13),('P2',ORANGE,'s',-.13)]:
   r=next(r for r in haz if r['spei_timescale']==scale and r['persistence_rule']==rule);x=float(r['roc_auc']);y=2-i+off
   d.scatter(x,y,c=col,marker=mark,s=34);d.text(x+.009,y,f'{x:.3f}',va='center',fontsize=8,color=col);record('Fig3','d',r,['roc_auc'])
 d.axvline(.5,color=GRAY,lw=.8,ls='--');d.text(.501,-.58,'Random = 0.5',fontsize=7,color=GRAY,ha='left')
 d.set(yticks=[2,1,0],yticklabels=['SPEI-1','SPEI-3','SPEI-6'],xlim=(.48,.72),ylim=(-.75,2.75),xlabel='Person-month ROC AUC');d.spines['left'].set_visible(False);d.tick_params(axis='y',length=0)
 d.legend(handles=[Line2D([],[],marker='o',color=BLUE,ls='',label='P1'),Line2D([],[],marker='s',color=ORANGE,ls='',label='P2')],fontsize=8,loc='upper center',ncol=2,frameon=False)
 save(fig,'Fig3_Stage2D')

def fig6():
 records=rows('SourceData_ExtendedDataFig3.xlsx','Functional_contrasts')
 comparisons=[('consensus_risk_ge2_vs_no_risk_consensus','Screen consensus versus none'),('incomplete_vs_recovered_before_next','Incomplete versus recovered'),('fire_overlap_vs_none','Fire overlap versus none'),('intact_vs_nonintact','Intact versus non-intact')]
 fig,axes=plt.subplots(2,2,figsize=(7.5,4.9));fig.subplots_adjust(left=.1,right=.97,bottom=.13,top=.9,hspace=.92,wspace=.35)
 for i,(key,title) in enumerate(comparisons):
  ax=axes.flat[i];heading(ax,chr(97+i),title)
  ax.axvline(0,c=GRAY,ls='--',lw=.8)
  for j,(metric,col,mark) in enumerate([('gpp_legacy',BLUE,'o'),('npp_legacy',ORANGE,'s')]):
   r=next(r for r in records if r['comparison']==key and r['metric']==metric);x,lo,hi=[float(r[k]) for k in ['difference_a_minus_b','ci_low','ci_high']];y=1-j
   ax.errorbar(x,y,xerr=[[x-lo],[hi-x]],fmt=mark,c=col,capsize=3,ms=5,lw=1.3)
   ax.text(x,y-.26,f'{x:.4f}',ha='center',va='top',color=col,fontsize=8)
   record('Fig6',chr(97+i),r,['difference_a_minus_b','ci_low','ci_high','n_a','n_b'])
  ax.set(yticks=[1,0],yticklabels=['GPP','NPP'],xlim=(-.033,.016),ylim=(-.62,1.55),xlabel=r'Legacy contrast (kg C m$^{-2}$ yr$^{-1}$)',xticks=[-.03,-.015,0,.015]);ax.tick_params(axis='x',labelsize=7.5)
  ax.spines['left'].set_visible(False);ax.tick_params(axis='y',length=0)
  ax.text(0,1.02,f"Group A / B: {int(r['n_a']):,} / {int(r['n_b']):,}",transform=ax.transAxes,fontsize=7.8,color=GRAY)
 save(fig,'Fig6_Stage2D')

def s4():
 with (INPUT_ROOT/'S5_Hminus1/S5_Category_Change.csv').open(encoding='utf-8-sig',newline='') as f:records=list(csv.DictReader(f))
 assert len(records)==20 and sum(r['grade_changed']=='True' for r in records)==0
 colors={'LIMITED':'#a6a6a6','CONDITIONAL':'#e88900','SUPPORTED':'#169b86'}
 fig=plt.figure(figsize=(8.5,7.6));g=fig.add_gridspec(1,4,width_ratios=[2.9,3.35,2.2,1.35],left=.025,right=.975,bottom=.115,top=.87,wspace=.13)
 lab,er,auc,nax=[fig.add_subplot(g[0,i]) for i in range(4)]
 for ax in [lab,er,auc,nax]:ax.set_ylim(-1,26);ax.set_yticks([])
 lab.axis('off');nax.axis('off');er.set(xlim=(-.05,4.6),xlabel='Median scale ER',xticks=[0,1,2,3,4]);auc.set(xlim=(.48,1),xlabel='Conditional event AUC',xticks=[.5,.6,.8,1])
 heading(er,'a','Enrichment ratio');heading(auc,'b','Strict-before AUC');heading(nax,'c','Support')
 nax.text(.98,25.9,'N_ER / N_AUC',ha='right',fontsize=7.4,color=GRAY)
 er.axvline(1,c=GRAY,ls='--',lw=.8);auc.axvline(.5,c=GRAY,ls='--',lw=.8);auc.axvline(.6,c=GRAY,ls=':',lw=.8)
 y=25
 for dim,title in [('forest_type','FOREST'),('climate_zone','CLIMATE'),('large_region','REGION'),('pilot_constraint','PILOT')]:
  lab.text(0,y,title,color=GRAY,fontsize=8.5,fontweight='bold');y-=.9
  for r in [r for r in records if r['group_dimension']==dim]:
   label=r['group'].replace(' forest','');label='Amazon historical pilot' if dim=='pilot_constraint' else label
   lab.text(.02,y,label,va='center',fontsize=8.1);col=colors[r['before_diagnostic_grade']]
   def num(k):
    try:return float(r[k])
    except (ValueError,TypeError):return math.nan
   x,lo,hi=[num(k) for k in ['original_ER','original_CI_low','original_CI_high']]
   if all(math.isfinite(v) for v in [x,lo,hi]):er.errorbar(x,y,xerr=[[x-lo],[hi-x]],fmt='o',color=col,ecolor=GRAY,ms=4.8,capsize=2,lw=.9)
   else:er.text(.02,y,'NA',fontsize=8,va='center',color=GRAY)
   a=num('AUC_H_minus1_median')
   if math.isfinite(a):
    auc.scatter(a,y,s=25,c=col);auc.text(a-.012,y+.20,f'{a:.3f}',ha='right',va='center',fontsize=7.1,color=INK)
   else:auc.text(.51,y,'NA',fontsize=8,va='center',color=GRAY)
   n,m=num('original_N_ER'),num('N_AUC');text=f'{n:,.0f} / {m:,.0f}' if math.isfinite(n) and math.isfinite(m) else 'Pilot / NA'
   nax.text(.98,y,text,ha='right',va='center',fontsize=7.9)
   for ax in [er,auc]:ax.axhline(y,c='#f0f1f3',lw=.4,zorder=0)
   record('FigS4',r['group'],r,['original_ER','original_CI_low','original_CI_high','original_N_ER','N_AUC','AUC_H_minus1_median','before_diagnostic_grade']);y-=1
  y-=.55
 fig.legend(handles=[Line2D([],[],color=c,marker='o',ls='',label=k.capitalize()) for k,c in colors.items()],loc='upper center',ncol=3,frameon=False,bbox_to_anchor=(.55,.992),fontsize=9)
 fig.text(.03,.045,'Conditional on the realized inter-drought horizon; not an unconditional drought-end forecast.',fontsize=8,color=GRAY)
 save(fig,'FigS4_Stage2D')

def main():
 global data,F,INPUT_ROOT
 p=argparse.ArgumentParser();p.add_argument('--data-root',type=Path,required=True);p.add_argument('--output-root',type=Path,required=True);p.add_argument('--figure',choices=['3','6','S4'],required=True);args=p.parse_args()
 INPUT_ROOT=args.data_root.resolve()/'09_EI_UPDATE';F=args.output_root.resolve()
 if F==args.data_root.resolve() or F.is_relative_to(args.data_root.resolve()):raise ValueError('Output must be outside the frozen input archive')
 F.mkdir(parents=True,exist_ok=True);data=json.loads((INPUT_ROOT/'figure_renderer_inputs/ei_renderer_tables.json').read_text(encoding='utf-8'))
 {'3':fig3,'6':fig6,'S4':s4}[args.figure]()
 (F/'plot_value_ledger.json').write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
if __name__=='__main__':main()
