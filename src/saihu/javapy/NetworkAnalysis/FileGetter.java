package NetworkAnalysis;

import org.json.JSONObject;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.net.URISyntaxException;

public class FileGetter {
    public static String file;
    public static String fileDir;
    public static String cplex_path;
    public static String lpsolve_path;

    public FileGetter(){
        try {
            file = FileGetter.class.getProtectionDomain().getCodeSource().getLocation().toURI().toString();
            if (file.startsWith("file:")) {
                // pass through the URL as-is, minus "file:" prefix
                file = file.substring(5);
            }
            fileDir = getDirName(file);
            getSolverPaths();
        } catch (URISyntaxException e) {
            e.printStackTrace();
        }
    }


    public String getDirName(String path){
        return new File(path).getParent();
    }

    public static Path join(String root, String... paths) {
        return Paths.get(root, paths);
    }

    public static void getSolverPaths() {
        Path pathFile = join(fileDir, "..", "resources", "paths.json");
        String jsonContentString = "{}";
        try {
            jsonContentString = Files.readString(pathFile);
        }
        catch (IOException ioe) {
            ioe.printStackTrace();
        }
        JSONObject paths = new JSONObject(jsonContentString);
        cplex_path = paths.optString("cplex");
        lpsolve_path = paths.optString("lpsolve");
    }
}
