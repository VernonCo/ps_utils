$(document).ready( function () {
    $('#refNumTR').hide();
            $('#refDateTR').hide();
    $('#queryType').change(function(){
        var opt = $(this).val();
        if (opt <= 2 ){
            $('#refNumTR').show();
            $('#refNum').attr('required', true);
            $('#refDateTR').hide();
            $('#refDate').removeAttr('required');
        }else{
            $('#refNumTR').hide();
            $('#refNum').removeAttr('required');
            $('#refDateTR').show();
            $('#refDate').attr('required', true);
        }
    } );
} );
