// Presentation semantics decide the surface, never untrusted model CSS.
export function surfaceFor(model) {
  if(model.compact || model.framed) return 'card';
  if(model.kind==='status' && model.refreshTransaction) return 'card';
  if(model.kind==='news' || model.kind==='status') return 'embedded';
  return 'projection';
}
