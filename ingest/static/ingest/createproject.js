function create_new_project() {
    const csrftoken = Cookies.get('csrftoken');
    const output_rows = [];
    
    const name = document.getElementById("name");
    const funded_by = document.getElementById("funded_by");

    output_rows.push({
        "name": name.value,
        "funded_by": funded_by.value
        })
  
    console.log(output_rows)
     
                
            
  fetch(`${window.origin}/ingest/create_project/`, {
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
