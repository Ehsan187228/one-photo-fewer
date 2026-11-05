/* cover_sa.c — simulated-annealing / local-search covering-design solver.
 *
 *   ./cover_sa V K T B MODE SEEDFILE SECS T0 RNGSEED OUTFILE
 *     MODE=shrink  : load SEEDFILE (m0 blocks, m0>=B), drop m0-B least-unique
 *                   blocks, anneal at B blocks until every t-set is covered.
 *     MODE=scratch : sampled-greedy B blocks from nothing, then anneal.
 *   SEEDFILE format: line 1 "v k t m0", then m0 lines of K ints.
 *
 * Move: block i, point p in it, point q outside; new block = old - p + q.
 *   t-sets = (T-1)-subset of (block\{p}) + p  lose one coverage;
 *   t-sets = (T-1)-subset of (block\{p}) + q  gain one.
 * Targeted move (72% when uncovered remain): pick a random uncovered t-set S,
 *   a random block with |S∩B|=t-1, and swap its excess point for S's missing
 *   point — directly repairs S.
 * Success (uncovered==0): independent full recount + duplicate scan, then
 *   OUTFILE gets "V K T B" + B lines of K ints. exit 0 ok / 1 fail / 2 usage.
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <stdint.h>
#include <time.h>

static uint64_t Cb[84][10];
static int V, K, T, B, W, NBMAX;
static uint64_t NTS;
static uint32_t *cnt, *upos, *uq, *tmpcnt;
static uint64_t usize;
static int *blk, *blk_best;
static uint64_t *bm, *bm_best;
static int CURB;
static int *combbuf; static int ncomb;      /* combos of [0..K) size T */
static int (*cvbuf)[9]; static int maxcv;   /* (T-1)-subsets of block\{p} */
static uint64_t best_unc;

static uint64_t rng_s;
static uint32_t *w;                 /* breakout weights per t-set */
static uint64_t Wobj, bestW;         /* weighted uncovered objective */
static uint64_t bo_count;
static inline uint64_t rnd(void){ rng_s ^= rng_s<<13; rng_s ^= rng_s>>7; rng_s ^= rng_s<<17; return rng_s; }
static inline double rnd01(void){ return (double)(rnd()>>11) * (1.0/9007199254740992.0); }
static double now_s(void){ struct timespec ts; clock_gettime(CLOCK_MONOTONIC,&ts); return ts.tv_sec+1e-9*ts.tv_nsec; }

static inline uint64_t rank_sorted(const int *a){ uint64_t r=0; for(int i=0;i<T;i++) r += Cb[a[i]-1][i+1]; return r; }
static void unrank(uint64_t r, int *a){
    for(int j=T-1;j>=0;j--){ int x=j+1; while(x<=V+1 && Cb[x-1][j+1]<=r) x++; a[j]=x-1; r-=Cb[x-2][j+1]; }
}
static inline void uq_add(uint64_t r){ uq[usize]=(uint32_t)r; upos[r]=(uint32_t)usize++; Wobj += w[r]; }
static inline void uq_del(uint64_t r){ uint64_t s=--usize; uint32_t j=upos[r]; Wobj -= w[r];
    if((uint64_t)j!=s){ uint32_t last=uq[s]; uq[j]=last; upos[last]=j; } }
static inline void dec_rank(uint64_t r){ uint32_t o=cnt[r]; cnt[r]=o-1; if(o==1) uq_add(r); }
static inline void inc_rank(uint64_t r){ uint32_t o=cnt[r]; cnt[r]=o+1; if(o==0) uq_del(r); }

static void set_block(int i, const int *pts){
    memcpy(blk+(size_t)i*K, pts, (size_t)K*sizeof(int));
    uint64_t *w=bm+(size_t)i*W; memset(w,0,(size_t)W*sizeof(uint64_t));
    for(int j=0;j<K;j++){ int p=pts[j]; w[p>>6] |= 1ULL<<(p&63); }
}
static void rebuild_from(int nb){
    memset(cnt,0,(size_t)NTS*sizeof(uint32_t));
    for(int i=0;i<nb;i++){ const int *pts=blk+(size_t)i*K; const int *cb=combbuf;
        for(int c=0;c<ncomb;c++,cb+=T){ int a[9]; for(int j=0;j<T;j++) a[j]=pts[cb[j]]; cnt[rank_sorted(a)]++; } }
    for(uint64_t r=0;r<NTS;r++) upos[r]=0xFFFFFFFFu;
    usize=0; Wobj=0;
    for(uint64_t r=0;r<NTS;r++) if(cnt[r]==0) uq_add(r);
}
static void apply_block(int sign, int i){
    const int *pts=blk+(size_t)i*K; const int *cb=combbuf;
    for(int c=0;c<ncomb;c++,cb+=T){ int a[9]; for(int j=0;j<T;j++) a[j]=pts[cb[j]];
        uint64_t r=rank_sorted(a); if(sign>0) inc_rank(r); else dec_rank(r); }
}

/* fresh independent recount (uses tmpcnt); returns uncovered count */
static uint64_t recount(int nb, const int *blocks){
    memset(tmpcnt,0,(size_t)NTS*sizeof(uint32_t));
    for(int i=0;i<nb;i++){ const int *pts=blocks+(size_t)i*K; const int *cb=combbuf;
        for(int c=0;c<ncomb;c++,cb+=T){ int a[9]; for(int j=0;j<T;j++) a[j]=pts[cb[j]]; tmpcnt[rank_sorted(a)]++; } }
    uint64_t u=0; for(uint64_t r=0;r<NTS;r++) if(tmpcnt[r]==0) u++;
    return u;
}

static int anneal(double secs, double T0, double Tend, uint64_t bo_n, int verbose){
    double t0=now_s(), lastlog=t0;
    uint64_t moves=0, evals=0, stag=0, bo=0; double Temp=T0;
    memcpy(blk_best, blk, (size_t)CURB*K*sizeof(int));
    best_unc=usize; bestW=Wobj;
    int A[9], Bq[9], nb[26];
    for(;;){
        double el=now_s()-t0; if(el>secs) break;
        Temp = T0*pow(Tend/T0, el/secs);
        if(usize==0) return 0;
        int i=-1,p=0,q=0;
        if(rnd01()<0.75){
            /* tournament pick: highest-weight uncovered t-set of 4 samples */
            uint64_t r0=uq[rnd()%usize];
            for(int k2=0;k2<3;k2++){ uint64_t r2=uq[rnd()%usize]; if(w[r2]>w[r0]) r0=r2; }
            int S[9]; unrank(r0, S);
            int cand[8192], nc=0;
            for(int j=0;j<CURB && nc<8192;j++){
                const uint64_t *w=bm+(size_t)j*W; int hit=0;
                for(int m=0;m<T;m++){ int p2=S[m]; if((w[p2>>6]>>(p2&63))&1ULL) hit++; }
                if(hit==T-1) cand[nc++]=j;
            }
            if(nc>0){
                i=cand[rnd()%nc];
                const uint64_t *wi=bm+(size_t)i*W; q=-1;
                for(int m=0;m<T;m++){ int p2=S[m]; if(!((wi[p2>>6]>>(p2&63))&1ULL)) q=p2; }
                const int *bi=blk+(size_t)i*K; int pool[26], np2=0;
                for(int m=0;m<K;m++){ int x=bi[m]; int inS=0;
                    for(int m2=0;m2<T;m2++) if(x==S[m2]){ inS=1; break; }
                    if(!inS) pool[np2++]=x; }
                p=pool[rnd()%np2];
            }
        }
        if(i<0){
            i=(int)(rnd()%(uint64_t)CURB);
            p=blk[(size_t)i*K + rnd()%(uint64_t)K];
            do { q=1+(int)(rnd()%(uint64_t)V); } while((bm[(size_t)i*W+(q>>6)]>>(q&63))&1ULL);
        }
        /* P = block\{p} (sorted, np points); collect its (T-1)-subsets into cvbuf */
        const int *bi=blk+(size_t)i*K;
        int P[26], np=0; for(int m=0;m<K;m++) if(bi[m]!=p) P[np++]=bi[m];
        int s=(int)Cb[np][T-1];
        int idx[9]; for(int m=0;m<T-1;m++) idx[m]=m;
        for(int c=0;c<s;c++){
            int *cv=cvbuf[c];
            for(int m=0;m<T-1;m++) cv[m]=P[idx[m]];
            if(c+1<s){ int m2=T-2; while(m2>=0 && idx[m2]==np-(T-1)+m2) m2--;
                if(m2<0) break; idx[m2]++; for(int m3=m2+1;m3<T-1;m3++) idx[m3]=idx[m3-1]+1; }
        }
        /* weighted tentative delta (breakout WLS objective) */
        uint64_t wbad=0, wgood=0;
        for(int c=0;c<s;c++){ const int *cv=cvbuf[c];
            { int z=0,m=0; while(m<T-1 && cv[m]<p) A[z++]=cv[m++]; A[z++]=p; while(m<T-1) A[z++]=cv[m++]; }
            { int z=0,m=0; while(m<T-1 && cv[m]<q) Bq[z++]=cv[m++]; Bq[z++]=q; while(m<T-1) Bq[z++]=cv[m++]; }
            uint64_t rA=rank_sorted(A), rB=rank_sorted(Bq);
            if(cnt[rA]==1) wbad += w[rA];
            if(cnt[rB]==0) wgood += w[rB];
        }
        int64_t wd=(int64_t)wbad-(int64_t)wgood;
        evals++;
        int acc = wd<0 ? 1 : (wd==0 ? (rnd01()<0.5) : (rnd01()<exp(-(double)wd/Temp)));
        if(acc){
            for(int c=0;c<s;c++){ const int *cv=cvbuf[c];
                { int z=0,m=0; while(m<T-1 && cv[m]<p) A[z++]=cv[m++]; A[z++]=p; while(m<T-1) A[z++]=cv[m++]; }
                { int z=0,m=0; while(m<T-1 && cv[m]<q) Bq[z++]=cv[m++]; Bq[z++]=q; while(m<T-1) Bq[z++]=cv[m++]; }
                dec_rank(rank_sorted(A)); inc_rank(rank_sorted(Bq));
            }
            { int z=0,m=0,qq=q; const int *old=blk+(size_t)i*K;
              while(m<K){ if(old[m]==p){ m++; continue; }
                  if(qq>0 && old[m]>qq){ nb[z++]=qq; qq=-1; continue; } nb[z++]=old[m++]; }
              if(qq>0) nb[z++]=qq; }
            set_block(i, nb);
            moves++;
            if(usize<best_unc){ best_unc=usize; memcpy(blk_best, blk, (size_t)CURB*K*sizeof(int)); }
        }
        if(Wobj<bestW){ bestW=Wobj; stag=0; } else stag++;
        if(stag>bo_n){
            /* BREAKOUT: raise the weight of every uncovered t-set.
             * stag counts EVALUATED moves (not accepted), so breakouts keep
             * firing even when the annealer is frozen at low temperature. */
            for(uint64_t z=0;z<usize;z++) w[uq[z]]++;
            Wobj += usize; bo++;
            if((bo&63)==0){ /* gentle periodic decay: equilibrium ~O(64) per stagnation window */
                for(uint64_t r=0;r<NTS;r++) if(w[r]>1) w[r]=1+((w[r]*3)>>2);
                uint64_t W2=0; for(uint64_t z=0;z<usize;z++) W2+=w[uq[z]]; Wobj=W2; }
            stag=0; }
        if(usize==0) return 0;
        if(verbose && now_s()-lastlog>5.0){ fprintf(stderr,"  [%6.1fs] unc=%llu best=%llu W=%llu T=%.3f mv=%llu ev=%llu bo=%llu\n", now_s()-t0,(unsigned long long)usize,(unsigned long long)best_unc,(unsigned long long)Wobj,Temp,(unsigned long long)moves,(unsigned long long)evals,(unsigned long long)bo); lastlog=now_s(); }
    }
    return 1;
}

static void die(const char*m,int c){ fprintf(stderr,"cover_sa: %s\n",m); exit(c); }

int main(int argc, char**argv){
    if(argc<10) die("usage: cover_sa V K T B shrink|scratch SEEDFILE SECS T0 RNGSEED OUTFILE",2);
    V=atoi(argv[1]); K=atoi(argv[2]); T=atoi(argv[3]); B=atoi(argv[4]);
    const char*mode=argv[5]; const char*sf=argv[6];
    double secs=atof(argv[7]); double T0=atof(argv[8]);
    rng_s=strtoull(argv[9],NULL,10)*0x9E3779B97F4A7C15ULL+1; if(!rng_s) rng_s=88172645463325252ULL;
    const char*of=argv[10]; (void)argc;
    if(V<8||V>80||K<T+1||K>26||T<2||T>5) die("params out of range",2);
    for(int n=0;n<84;n++){ Cb[n][0]=1; for(int r=1;r<10;r++) Cb[n][r]= r>n?0:Cb[n-1][r-1]+Cb[n-1][r]; }
    NTS=Cb[V][T]; W=(V+63)/64;
    ncomb=(int)Cb[K][T]; maxcv=(int)Cb[K-1][T-1];
    if(NTS>30000000u) die("state too large",2);
    cnt=calloc(NTS,4); upos=malloc((size_t)NTS*4); uq=malloc((size_t)NTS*4); tmpcnt=malloc((size_t)NTS*4);
    w=malloc((size_t)NTS*4); if(!w) die("oom w",2); for(uint64_t r=0;r<NTS;r++) w[r]=1;
    combbuf=malloc((size_t)ncomb*T*sizeof(int)); cvbuf=malloc((size_t)(maxcv>1?maxcv:1)*sizeof(*cvbuf));
    if(!cnt||!upos||!uq||!tmpcnt||!combbuf||!cvbuf) die("oom",2);
    { int c=0, idx[9]; for(int i=0;i<T;i++) idx[i]=i;
      while(1){ for(int i=0;i<T;i++) combbuf[(size_t)c*T+i]=idx[i]; c++;
        int i=T-1; while(i>=0 && idx[i]==K-T+i) i--; if(i<0) break;
        idx[i]++; for(int j=i+1;j<T;j++) idx[j]=idx[j-1]+1; } }
    int m0=0;
    if(!strcmp(mode,"shrink")){
        FILE*f=fopen(sf,"r"); if(!f) die("cannot open seedfile",2);
        int v,k,t; if(fscanf(f,"%d %d %d %d",&v,&k,&t,&m0)!=4||v!=V||k!=K||t!=T||m0<B) die("bad seedfile header",2);
        NBMAX=m0;
        blk=malloc((size_t)NBMAX*K*sizeof(int)); bm=calloc((size_t)NBMAX*W,8);
        blk_best=malloc((size_t)NBMAX*K*sizeof(int)); bm_best=malloc((size_t)NBMAX*W*8);
        for(int i=0;i<m0;i++){ int pts[26]; for(int j=0;j<K;j++){ if(fscanf(f,"%d",&pts[j])!=1) die("bad seedfile body",2); }
            /* sort */ for(int a=1;a<K;a++){ int x=pts[a],b=a-1; while(b>=0&&pts[b]>x){pts[b+1]=pts[b];b--;} pts[b+1]=x; }
            set_block(i, pts); }
        fclose(f);
        CURB=m0; rebuild_from(CURB);
        if(recount(CURB, blk)!=0) die("seed is not a covering?!",2);
        /* drop m0-B blocks, each time one with fewest uniquely-covered t-sets */
        while(CURB>B){
            int besti=-1; uint64_t bestu=UINT64_MAX;
            for(int i=0;i<CURB;i++){
                const int *pts=blk+(size_t)i*K; const int *cb=combbuf; uint64_t u=0;
                for(int c=0;c<ncomb;c++,cb+=T){ int a[9]; for(int j=0;j<T;j++) a[j]=pts[cb[j]];
                    if(cnt[rank_sorted(a)]==1) u++; }
                if(u<bestu || (u==bestu && (rnd()&1))){ bestu=u; besti=i; }
            }
            apply_block(-1, besti);
            memmove(blk+(size_t)besti*K, blk+(size_t)(CURB-1)*K, (size_t)K*sizeof(int));
            { uint64_t *a=bm+(size_t)besti*W, *b=bm+(size_t)(CURB-1)*W; memcpy(a,b,(size_t)W*8); }
            CURB--;
        }
    } else if(!strcmp(mode,"scratch")){
        NBMAX=B;
        blk=malloc((size_t)NBMAX*K*sizeof(int)); bm=calloc((size_t)NBMAX*W,8);
        blk_best=malloc((size_t)NBMAX*K*sizeof(int)); bm_best=malloc((size_t)NBMAX*W*8);
        memset(upos,0xFF,(size_t)NTS*4); usize=0; Wobj=0;
        for(uint64_t r=0;r<NTS;r++){ uq[r]=(uint32_t)r; upos[r]=(uint32_t)r; } usize=NTS; Wobj=NTS;
        int M=(int)(Cb[K][T]>20000? 32 : (Cb[K][T]>2000? 128:512));
        int cand[26];
        for(int step=0; step<B && CURB<B; step++){
            uint64_t bestgain=UINT64_MAX; int bestcand[26];
            for(int tr=0;tr<M;tr++){
                for(int j=0;j<K;j++) cand[j]=1+(int)(rnd()%(uint64_t)V);
                for(int a=1;a<K;a++){ int x=cand[a],b=a-1; while(b>=0&&cand[b]>x){cand[b+1]=cand[b];b--;} cand[b+1]=x; }
                { int bad=0; for(int a=1;a<K;a++) if(cand[a]==cand[a-1]) bad=1; if(bad){ tr--; continue; } }
                const int *cb=combbuf; uint64_t gain=0;
                for(int c=0;c<ncomb;c++,cb+=T){ int a[9]; for(int j=0;j<T;j++) a[j]=cand[cb[j]];
                    if(cnt[rank_sorted(a)]==0) gain++; }
                if(gain>bestgain){ bestgain=gain; memcpy(bestcand,cand,(size_t)K*sizeof(int)); }
            }
            set_block(CURB, bestcand); apply_block(+1, CURB); CURB++;
            if(usize==0) break;
        }
        rebuild_from(CURB);
    } else die("mode?",2);
    fprintf(stderr,"cover_sa: v%d k%d t%d b=%d start unc=%llu (of %llu)\n",V,K,T,CURB,(unsigned long long)usize,(unsigned long long)NTS);
    int rc=anneal(secs, T0, 0.03, 6000u + 60u*(uint64_t)CURB, 1);
    if(rc!=0){ /* consistency: independent recount must match the tracked best */
        uint64_t chk=recount(CURB, blk_best);
        fprintf(stderr,"consistency: recount(best)=%llu tracked=%llu %s\n",(unsigned long long)chk,(unsigned long long)best_unc, chk==best_unc?"OK":"MISMATCH!");
    }
    if(rc==0){
        /* independent recheck: recount + duplicate scan + validity */
        if(recount(CURB, blk)!=0){ fprintf(stderr,"RECHECK FAILED: uncovered\n"); return 1; }
        for(int i=0;i<CURB;i++) for(int j=i+1;j<CURB;j++){
            const uint64_t *a=bm+(size_t)i*W,*b=bm+(size_t)j*W; int eq=1;
            for(int w2=0;w2<W;w2++) if(a[w2]!=b[w2]){eq=0;break;}
            if(eq){ fprintf(stderr,"RECHECK FAILED: duplicate blocks %d,%d\n",i,j); return 1; } }
        for(int i=0;i<CURB;i++){ const int *pts=blk+(size_t)i*K;
            for(int j=0;j<K;j++) if(pts[j]<1||pts[j]>V||(j&&pts[j]<=pts[j-1])){ fprintf(stderr,"RECHECK FAILED: bad block\n"); return 1; } }
        FILE*f=fopen(of,"w"); if(!f) die("cannot write outfile",2);
        fprintf(f,"%d %d %d %d\n",V,K,T,CURB);
        for(int i=0;i<CURB;i++){ const int *pts=blk+(size_t)i*K;
            for(int j=0;j<K;j++) fprintf(f,"%d%c",pts[j],j==K-1?'\n':' '); }
        fclose(f);
        printf("RESULT ok v=%d k=%d t=%d b=%d\n",V,K,T,CURB);
        return 0;
    }
    printf("RESULT fail v=%d k=%d t=%d b=%d best_unc=%llu\n",V,K,T,CURB,(unsigned long long)best_unc);
    return 1;
}
