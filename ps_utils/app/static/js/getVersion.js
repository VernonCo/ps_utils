/* get and set the latest version available for the selected company */
function getVersion(){var selectedCompanyID = $("#companyID").children("option:selected").val();$.post("/inventory/getVersion/", {companyID:selectedCompanyID},function (data, textStatus, jqXHR) {if (data.version === "2"){$("#service_version").val("V2");}else{ $("#service_version").val("V1");}},"json");}
$(document).ready( function () {if ($("#companyID").val()){getVersion();}$("#companyID").change(function(){getVersion();});});
