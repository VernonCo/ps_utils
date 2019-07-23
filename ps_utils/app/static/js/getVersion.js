/* get and set the latest version available for the selected company */
function getVersion(){var selectedcompanyID = $("#companyID").children("option:selected").val();$.post("/inventory/getVersion/", {companyID:selectedcompanyID},function (data, textStatus, jqXHR) {if (data.version === "2"){$("#serviceVersion").val("V2");}else{ $("#serviceVersion").val("V1");}},"json");}
$(document).ready( function () {getVersion();$("#companyID").change(function(){getVersion();});});
