function link_collection_and_project() {
    const csrftoken = Cookies.get('csrftoken');
    const output_rows = [];
    
    const project_id = document.getElementById("project_id");
    const collection_id = document.getElementById("collection_id");

    output_rows.push({
        "project_id": project_id.value,
        "collection_id": collection_id.value
        })
  
    console.log(output_rows)
     
                
            
  fetch(`${window.origin}/ingest/descriptive_metadata_upload/`, {
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
