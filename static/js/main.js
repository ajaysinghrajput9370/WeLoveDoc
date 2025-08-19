$(document).ready(function(){
  $('#signup-btn').click(function(){ $('#subscription-popup').show(); });
  $('#cancel-btn').click(function(){ $('#subscription-popup').hide(); });
  $('#subscribe-btn').click(function(){
    alert('Subscription successful!');
    $('#subscription-popup').hide();
  });
});
