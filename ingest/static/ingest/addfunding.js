function create_funding() {
    const csrftoken = Cookies.get('csrftoken');
    const output_rows = [];
    
    const project = document.getElementById("project");
    const funder_name = document.getElementById("funder_name");
    const funder_ref_id = document.getElementById("funder_ref_id");
    const funder_ref_type = document.getElementById("funder_ref_type");
    const funder_award_num = document.getElementById("funder_award_num");
    const funder_award_title = document.getElementById("funder_award_title");

    output_rows.push({
        "project": project.value,
        "funder_name": funder_name.value,
        "funder_ref_id": funder_ref_id.value,
        "funder_ref_type": funder_ref_type.value,
        "funder_award_num": funder_award_num.value,
        "funder_award_title": funder_award_title
        })
  
    console.log(output_rows)
     
                
            
  fetch(`${window.origin}/ingest/create_funding/`, {
       method: "POST",
       credentials: "include",
       body: JSON.stringify(output_rows),
       cache: "no-cache",
       headers: new Headers({
           "X-CSRFToken": csrftoken,
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
