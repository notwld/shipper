$(document).ready(function() {


    $("li:first-child").addClass("first");
    $("li:last-child").addClass("last");
    
    $('[href="#"]').attr("href", "javascript:;");
    $('.menu-Bar').click(function() {
        $(this).toggleClass('open');
        $('.menuWrap').toggleClass('open');
        $('body').toggleClass('ovr-hiddn');
        $('body').toggleClass('overflw');
    });

});

$(window).on('load', function() {
    var currentUrl = window.location.href.substr(window.location.href.lastIndexOf("/") + 1);
    $('ul.menu li a').each(function() {
        var hrefVal = $(this).attr('href');
        if (hrefVal == currentUrl) {
            $(this).removeClass('active');
            $(this).closest('li').addClass('active')
            $('ul.menu li.first').removeClass('active');
             
        }
    });
    
});

function positionItems() {
  var container = $('#container'),
      fields = $('.item'),
      width = container.width(),
      height = container.height(),
      radius = (width / 2) - (fields.width() / 2); // Responsive radius calculation

  var angle = 0,
      step = (2 * Math.PI) / fields.length;

  fields.each(function() {
    var x = Math.round(width / 2 + radius * Math.cos(angle) - $(this).width() / 2);
    var y = Math.round(height / 2 + radius * Math.sin(angle) - $(this).height() / 2);
    if (window.console) {
      console.log($(this).text(), x, y);
    }
    $(this).css({
      left: x + 'px',
      top: y + 'px'
    });
    angle += step;
  });
}

// Initial position
positionItems();

// Reposition items on window resize
$(window).resize(function() {
  positionItems();
});

$(document).ready(function() {

  $(".show_hide_password a").on('click', function(event) {
      event.preventDefault();
      if($('.show_hide_password input').attr("type") == "text"){
          $('.show_hide_password input').attr('type', 'password');
          $('.show_hide_password i').addClass( "fa-eye-slash" );
          $('.show_hide_password i').removeClass( "fa-eye" );
      }else if($('.show_hide_password input').attr("type") == "password"){
          $('.show_hide_password input').attr('type', 'text');
          $('.show_hide_password i').removeClass( "fa-eye-slash" );
          $('.show_hide_password i').addClass( "fa-eye" );
      }
  });
});
