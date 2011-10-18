$(document).ready(function() {
  $('a').click(function(){
    var url = $(this).attr('href');
    window.location.href = add_parameter_to_url(url, 'fancybox=1');
    return false;
  });
});
