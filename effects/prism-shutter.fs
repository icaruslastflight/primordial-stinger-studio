/*{
  "ISFVSN": "2",
  "DESCRIPTION": "A full-frame diagonal shutter closes, holds a clear logo, and opens. The center hold provides an opaque cut window.",
  "CREDIT": "Primordial / Brice Morneau \u2014 curated studio studies",
  "CATEGORIES": [
    "Stinger",
    "Primordial"
  ],
  "INPUTS": [
    {
      "NAME": "inputImage",
      "TYPE": "image",
      "LABEL": "Logo"
    },
    {
      "NAME": "uProgress",
      "TYPE": "float",
      "LABEL": "Cue Progress",
      "DEFAULT": 0.45,
      "MIN": 0,
      "MAX": 1
    },
    {
      "NAME": "uLoop",
      "TYPE": "bool",
      "LABEL": "Self-Run Loop",
      "DEFAULT": true
    },
    {
      "NAME": "uDuration",
      "TYPE": "float",
      "LABEL": "Transition Duration",
      "DEFAULT": 2.4,
      "MIN": 0.6,
      "MAX": 6
    },
    {
      "NAME": "uIntensity",
      "TYPE": "float",
      "LABEL": "Light Intensity",
      "DEFAULT": 0.7,
      "MIN": 0,
      "MAX": 1
    },
    {
      "NAME": "uTint",
      "TYPE": "color",
      "LABEL": "Primary Light",
      "DEFAULT": [
        0.75,
        0.95,
        0.5,
        1
      ]
    },
    {
      "NAME": "uTint2",
      "TYPE": "color",
      "LABEL": "Accent Light",
      "DEFAULT": [
        0.3,
        0.65,
        0.8,
        1
      ]
    },
    {
      "NAME": "uLumaKey",
      "TYPE": "bool",
      "LABEL": "Luma Key",
      "DEFAULT": false
    },
    {
      "NAME": "uAudioReact",
      "TYPE": "float",
      "LABEL": "Audio Response",
      "DEFAULT": 0.3,
      "MIN": 0,
      "MAX": 1
    },
    {
      "NAME": "uBass",
      "TYPE": "float",
      "LABEL": "Audio Bass",
      "DEFAULT": 0,
      "MIN": 0,
      "MAX": 1
    }
  ]
}*/

float easeOut(float t){return 1.-pow(1.-clamp(t,0.,1.),3.);}
vec4 mark(vec2 q){
 vec2 s=clamp(q,0.,1.);vec4 c=IMG_NORM_PIXEL(inputImage,s);
 float inside=step(0.,q.x)*step(q.x,1.)*step(0.,q.y)*step(q.y,1.);
 if(uLumaKey)c.a*=smoothstep(.035,.25,max(c.r,max(c.g,c.b)));
 return vec4(c.rgb,c.a*inside);
}
float edgeAt(vec2 q){vec2 e=vec2(1.6)/RENDERSIZE;
 float a=mark(q).a;float nearA=max(max(mark(q+vec2(e.x,0.)).a,mark(q-vec2(e.x,0.)).a),max(mark(q+vec2(0.,e.y)).a,mark(q-vec2(0.,e.y)).a));
 float farA=min(min(mark(q+vec2(e.x,0.)).a,mark(q-vec2(e.x,0.)).a),min(mark(q+vec2(0.,e.y)).a,mark(q-vec2(0.,e.y)).a));
 return max(nearA-a,a-farA);
}
void outputPM(vec3 rgb,float alpha){
 alpha=clamp(alpha,0.,1.);rgb=clamp(rgb,0.,alpha);
#ifdef VJ_PREMULT
 gl_FragColor=vec4(rgb,alpha);
#else
 gl_FragColor=vec4(rgb/max(alpha,.00001),alpha);
#endif
}
void main(){
 float duration=max(.6,uDuration);float progress=uLoop?mod(TIME,duration*1.65)/duration:uProgress;
 if(progress<=0.||progress>=1.){gl_FragColor=vec4(0.);return;}
 vec2 uv=isf_FragNormCoord;vec2 p=(uv-.5)*vec2(RENDERSIZE.x/RENDERSIZE.y,1.);
 float enter=easeOut(progress/.26),leave=smoothstep(.74,1.,progress),visible=enter*(1.-leave);
 float audio=clamp(uBass*uAudioReact,0.,1.);vec3 primary=uTint.rgb,accent=uTint2.rgb;
 vec4 logo=mark(uv);vec3 rgb=vec3(0.);float alpha=0.;

 float cover=enter*(1.-leave);float axis=abs(p.x+p.y*.55)/1.5;float edgeWidth=2./RENDERSIZE.y;
 float mask=1.-smoothstep(cover-edgeWidth,cover+edgeWidth,axis);
 float lead=exp(-pow((axis-cover)/.007,2.))*uIntensity;
 vec3 plate=mix(primary*.10,accent*.16,clamp(uv.y,0.,1.));
 plate+=primary*(.018+.015*sin((p.x-p.y)*40.));
 float logoFade=smoothstep(.22,.36,progress)*(1.-smoothstep(.66,.78,progress));
 alpha=mask;rgb=plate*mask+primary*lead*mask*.65;
 rgb=mix(rgb,logo.rgb*mask,logo.a*logoFade);

 outputPM(rgb,alpha);
}
