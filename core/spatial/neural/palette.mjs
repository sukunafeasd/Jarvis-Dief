// Preserve lighting contrast while using the same live tint as the real core.
export const neuralPaletteGLSL=`
uniform vec3 uTint,uAccent;
vec3 neuralLight(vec3 light){
  float energy=max(light.r,max(light.g,light.b));
  float white=min(light.r,min(light.g,light.b))/max(.001,energy);
  float signal=step(light.r+.08,min(light.g,light.b));
  return mix(uTint,uAccent,max(signal*.78,white*.65))*energy;
}
`;
