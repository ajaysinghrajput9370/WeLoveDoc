// simple device fingerprint (placeholder)
(function(){
  const fp = btoa(navigator.userAgent + '|' + screen.width + 'x' + screen.height);
  const el = document.getElementById('fingerprint');
  if (el) el.value = fp;
})();
