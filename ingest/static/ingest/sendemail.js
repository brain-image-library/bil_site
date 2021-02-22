function collection_send() {
  const rowform = document.getElementById("rowform");
  const all_names = rowform.elements["name"]
  const all_descriptions = rowform.elements["description"]
  const all_organization_labs = rowform.elements["organization_lab"]
  const all_lab_names = rowform.elements["lab_name"]
  const all_project_funder_ids = rowform.elements["project_funder_id"]
  const all_project_funders = rowform.elements["project_funder"]
  const all_bil_uuids = rowform.elements["bil_uuid"]
  const all_data_path = rowform.elements["data_path"]
  const all_locked = rowform.elements["locked"]
  const all_submission_statuses = rowform.elements["submission_status"]
  const all_validation_statuses = rowform.elements["validation_status"]
  let output_rows = []
  for(let i = 0; i < all_names.length; i++)
  {
      const rowdata = {
          name: all_names[i].value,
          description: all_descriptions[i].value,
          organization_lab: all_organization_labs[i].value,
          lab_name: all_lab_names[i].value,
          project_funder_id: all_project_funder_ids[i].value,
          project_funder: all_project_funders[i].value,
          bil_uuid: all_bil_uuids[i].value,
          data_path: all_data_path[i].value,
          locked: all_locked[i].value,
          submission_status: all_submission_statuses[i].value,
          validation_status: all_validation_statuses[i].value,
      };
      output_rows.push(rowdata);
  }
  console.log(output_rows);
  fetch('${window.origin}/collection_send', {
      method: "POST",
      credentials: "include",
      body: JSON.stringify(output_rows),
      cache: "no-cache",
      headers: new Headers({
          "content-type": "application/json"
      })
  })
      .then(function(response) {
          if (response.status !== 200) {
              console.log('Looks like there was a problem. Status code: ${response.status}');
              return;
          }
              response.json().then(function(data) {
              console.log(data);
              window.location.replace(data['url']);
          });  
      })
      .catch(function(error) {
          console.log("Fetch error: " + error);
   
  });
} 

