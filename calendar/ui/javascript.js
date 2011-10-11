$(document).ready(function(){
  // Hide add event buttons
  $(".add-event-area .add-event").hide();
  // Intercept clicks on events
  $(".event").click(function(e){
    var target  = $(e.target);
    if( target.is('a') ) {
      var link = target.attr('href');
    }else if( target.is('img') ) {
      var link = target.parent.attr('href');
    }else{
      var link = $(this).children('.event-link:first').attr('href');
    }
    $(location).attr('href', link);
    return false;
  });
  // Intercept clicks on add-event-area
  $(".add-event-area").click(function(e){
    var target  = $(e.target);
    if( target.is('img') ) {
      var link = target.parent.attr('href');
    }else{
      var link = $(this).children('.add-event').attr('href');
    }
    $(location).attr('href', link);
    return false;
  });
});

function update_rrule_parameters(){
  if ($("#rrule").val() == ""){
      /* Hide parameters fields */
      $(".block-widget-rrule_interval").hide();
  }
  else {
      $(".block-widget-rrule_interval").show();
  };
};
