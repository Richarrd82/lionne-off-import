// Pure comparison/presentation rules; no rounding of stored measurements.
// Display formatting never changes the stored nutrition or label quotes.
export function formatOFFValue(value){
 if(value==null||value==='')return 'Unknown';
 const n=typeof value==='number'?value:Number(String(value).replace(',','.'));
 return Number.isFinite(n)?new Intl.NumberFormat('en-GB',{maximumSignificantDigits:12}).format(n):String(value);
}
export function offValueDifference(field,source,label){
 if(typeof source!=='number'||typeof label!=='number'||!Number.isFinite(source)||!Number.isFinite(label))return 'unknown';
 const delta=Math.abs(source-label);
 if(delta<=Math.max(1e-6,Math.max(Math.abs(source),Math.abs(label))*1e-7))return 'same';
 if(source>0&&label>0&&delta<=(field==='kcal'?1:.1)+1e-9&&delta<=.02*Math.min(source,label)+1e-9)return 'minor';
 return 'changed';
}
