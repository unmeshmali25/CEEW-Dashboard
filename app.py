import base64
import os
from urllib.parse import quote as urlquote

from flask import Flask, send_from_directory
import dash
import dash_core_components as dcc
import dash_html_components as html
import dash_bootstrap_components as dbc
from dash.dependencies import Input, Output, State
import os
import dash_table
from imageai.Detection import ObjectDetection
import pandas as pd
from dash.exceptions import PreventUpdate

UPLOAD_DIRECTORY = "./app_uploaded_files"


img_folder = UPLOAD_DIRECTORY
models = './'
output = './outputs/'



# Initialize the model
detector = ObjectDetection()
model_path = models+'yolo.h5'
detector.setModelTypeAsYOLOv3()


#Load the model
detector.setModelPath(model_path)
detector.loadModel()

if not os.path.exists(UPLOAD_DIRECTORY):
    os.makedirs(UPLOAD_DIRECTORY)

for f in os.listdir(UPLOAD_DIRECTORY):
    os.remove(os.path.join(UPLOAD_DIRECTORY, f))

# Normally, Dash creates its own Flask server internally. By creating our own,
# we can create a route for downloading files directly:
server = Flask(__name__)
app = dash.Dash(server=server, external_stylesheets=[dbc.themes.DARKLY])


for f in os.listdir(UPLOAD_DIRECTORY):
    os.remove(os.path.join(UPLOAD_DIRECTORY, f))

@server.route("/download/<path:path>")
def download(path):
    """Serve a file from the upload directory."""
    return send_from_directory(UPLOAD_DIRECTORY, path, as_attachment=True)


app.layout = html.Div([
    html.Div(
    children = [
        html.Div(html.H1("CEEW - Rapid Bus Shelter Assessment"), style={'color' : 'white', 'fontSize': 14, 'textAlign': 'center', 'marginBottom' : '3em', 'marginTop' : '2em'}) ,
        html.H5("Upload file/files for assessment of safety and accessiblity"),
        dcc.Upload(
            id="upload-data",
            children=html.Div(
                ["Drag and drop or click to select a file to upload."]
            ),
            style={
                "width": "30%",
                "height": "60px",
                "lineHeight": "60px",
                "borderWidth": "1px",
                "borderStyle": "dashed",
                "borderRadius": "5px",
                "textAlign": "center",
                "margin": "10px",
                "marginBottom": "40px",
            },
            multiple=True,
        )], 
        style = {'vertical-align': 'top'}),
html.Div(children = [
        html.H5("Names of bus shelters uploaded (Click on image link to download)"),
        html.Ul(id="file-list"),
], style={'display': 'inline-block', 'vertical-align': 'top', 'marginRight' : '20em'}),


html.Div(children = [ 
        html.Button('Press to generate labels', id='submit-val', n_clicks=0, style = {'marginBottom' : '3em'}),
        html.H5("Summary Table", style = {'marginBottom' : '1em'}),
        html.Div(id = 'summary_table', style = {'marginBottom' : '3em'}),
        html.Div(id = "accessibilit_safety_table"),

    ],style={'display': 'inline-block', 'vertical-align': 'top'})
,])


def save_file(name, content):
    """Decode and store a file uploaded with Plotly Dash."""
    data = content.encode("utf8").split(b";base64,")[1]
    with open(os.path.join(UPLOAD_DIRECTORY, name), "wb") as fp:
        fp.write(base64.decodebytes(data))


def uploaded_files():
    """List the files in the upload directory."""
    files = []
    for filename in os.listdir(UPLOAD_DIRECTORY):
        path = os.path.join(UPLOAD_DIRECTORY, filename)
        if os.path.isfile(path):
            files.append(filename)
    return files



def file_download_link(filename):
    """Create a Plotly Dash 'A' element that downloads a file from the app."""
    location = "/download/{}".format(urlquote(filename))
    return html.A(filename, href=location)


def parse_contents(contents, filename):
    return html.Div([
        html.H5(filename),
        # HTML images accept base64 encoded strings in the same format
        # that is supplied by the upload
        html.Img(src=contents),
        html.Hr(),
    ])


@app.callback(
    Output("file-list", "children"),
    [Input("upload-data", "filename"), Input("upload-data", "contents")],
)
def update_output(uploaded_filenames, uploaded_file_contents):
    """Save uploaded files and regenerate the file list."""

    if uploaded_filenames is not None and uploaded_file_contents is not None:
        for name, data in zip(uploaded_filenames, uploaded_file_contents):
            save_file(name, data)

    files = uploaded_files()
    if len(files) == 0:
        return [html.Li("No files yet!")]
    else:
        return [html.Li(file_download_link(filename)) for filename in files]

    
@app.callback([Output('accessibilit_safety_table', 'children'),
                Output('summary_table', 'children')],
    
              [Input('submit-val', 'n_clicks')], 
              [State("upload-data", "filename"), State("upload-data", "contents")])
def update_output(n_clicks, list_of_names, list_of_contents):
    summary_df = pd.DataFrame()
    final_df = pd.DataFrame()

    if list_of_contents is None:
        raise PreventUpdate

    x = zip(list_of_names, list_of_contents)
    df = pd.DataFrame()
    for n,c in x:
        input_road = os.path.join(UPLOAD_DIRECTORY, n)
        output_path = os.path.join(output, n)
        print(input_road)
        print(output_path)
        detection = detector.detectObjectsFromImage(input_image=input_road, output_image_path=output_path)
        d = pd.DataFrame(detection)
        d['bus_shelter_name'] = n
        df = df.append(pd.DataFrame(d))
    box_point = df["box_points"].tolist()
    x=[]
    for i in box_point:
        d=(i[3]-i[1])*(i[2]-i[0])
        x.append(d)

    area={"Area":x}
    df1=pd.DataFrame(area)
    df=df.join(df1)

    # Rule 1: If there's a car in the frame (detected as an object), check it's area relative to the threshold. 
#         This helps to see if the car detected is actually blocking the bus stop. 
    accessibility = {}
    safety = {}
    print("Printing unique images in df after appending...")
    print(df['bus_shelter_name'].unique())
    for image in df['bus_shelter_name'].unique():
        df_sub = df[df['bus_shelter_name'] == image]
        
        total_presence = len(df_sub[df_sub['name'] == 'car'])
        if total_presence:
            y=df_sub[df_sub["Area"]>2000]  # you can change the Threshold value of the area as per above dataframe
            d=y['name']
            for i in d:
                if('car'==i):
                    
                    accessibility[image] = 'Inaccessible'
                    #accessiblity.append({image : 'Not Accessible'})
                    print('\x1b[1;60m'+'Inaccessible'+'\x1b[0m')
                    print("Because of the",i)
                    break
        else: 
            accessibility[image] = 'Accessible'
            print('\x1b[1;60m'+'Accessible'+'\x1b[0m')


        # If animals are present in the frame, better mark the bus shelter as unsafe. 
        animals_present = df_sub['name'].str.contains("cow|dog").any()
        if animals_present:
            safety[image] = 'Unsafe'
            print('\x1b[1;60m'+'Unsafe'+'\x1b[0m')
        else:
            safety[image] = 'Safe'
    #print(accessiblity)
    

    safety_df = pd.DataFrame(safety.items(), columns=['Bus Shelter Name', 'Safety Label'])
    accessibility_df = pd.DataFrame(accessibility.items(), columns=['Bus Shelter Name', 'Accessibility Label'])
    print("Printing safety table")
    print(safety_df)
    print("Printing accessibility table")
    print(accessibility_df)
    final_df = safety_df.merge(accessibility_df, on = 'Bus Shelter Name', how = 'left')
    print(final_df)

    # Return Summary Table

    unsafe_count = final_df['Safety Label'].str.count('Unsafe').sum()
    safe_count = final_df['Safety Label'].str.count('Safe').sum()

    accessible_count = final_df['Accessibility Label'].str.count('Accessible').sum()
    inaccessible_count = final_df['Accessibility Label'].str.count('Inaccessible').sum()
    summary_df = pd.DataFrame([{'Label': 'Unsafe Bus Sheltes', 
         'Count' : unsafe_count}, 
              {'Label': 'Safe Bus Shelters', 
         'Count' : safe_count}, 
         {'Label': 'Accessible Bus Shelters', 
         'Count' : accessible_count}, 
         {'Label': 'Inaccessible Bus Shelters', 
         'Count' : inaccessible_count}, ])
    summary_df.set_index('Label', inplace = True)
    summary_df.reset_index(inplace = True)
    print(summary_df)

    return (html.Div([
                dash_table.DataTable(
                    data=final_df.to_dict('records'),
                    columns=[{'name': i, 'id': i, 'id': i} for i in final_df.columns], 
                    style_header={
                'backgroundColor': 'rgb(50, 50, 50)',
                'fontWeight': 'bold'
            },
            style_cell={
                'backgroundColor': 'rgb(50, 50, 50)',
                'color': 'white'
             },
                )
                ]), html.Div([
                dash_table.DataTable(
                    data=summary_df.to_dict('records'),
                    columns=[{'name': i, 'id': i} for i in summary_df.columns], 
                    style_header={
                'backgroundColor': 'rgb(50, 50, 50)',
                'fontWeight': 'bold'
            },
            style_cell={
                'backgroundColor': 'rgb(50, 50, 50)',
                'color': 'white'
             },
                )
                ]))


if __name__ == "__main__":
    app.run_server(debug=True)
