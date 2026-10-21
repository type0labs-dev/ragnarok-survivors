// Projeto Unity de apoio (~/vs-decomp/unity-audio): importa os WAV de Assets/Audio como Vorbis em memória (o mesmo
// formato das músicas do VS: mono, 44,1 kHz, CompressedInMemory) e gera um AssetBundle por clipe. O FSB5 de dentro
// do .resource é o que o tools/build_music.py transplanta pros bundles do Switch.
// uso: Unity -batchmode -nographics -quit -projectPath <proj> -executeMethod BuildAudio.Run -out <pasta> [-quality 0.5]
using System.IO;
using UnityEditor;
using UnityEngine;

public static class BuildAudio
{
    public static void Run()
    {
        string[] args = System.Environment.GetCommandLineArgs();
        string outDir = "AudioOut";
        float quality = 0.5f;
        string format = "vorbis";  // vorbis = músicas; adpcm = efeitos (o formato dos clipes do resources.resource)
        for (int i = 0; i < args.Length - 1; i++)
        {
            if (args[i] == "-out") outDir = args[i + 1];
            if (args[i] == "-format") format = args[i + 1];
            if (args[i] == "-quality") quality = float.Parse(args[i + 1], System.Globalization.CultureInfo.InvariantCulture);
        }
        Directory.CreateDirectory(outDir);
        var builds = new System.Collections.Generic.List<AssetBundleBuild>();
        foreach (string path in Directory.GetFiles("Assets/Audio", "*.wav"))
        {
            var imp = (AudioImporter)AssetImporter.GetAtPath(path);
            var s = imp.defaultSampleSettings;
            s.loadType = AudioClipLoadType.CompressedInMemory;
            s.compressionFormat = format == "adpcm" ? AudioCompressionFormat.ADPCM : AudioCompressionFormat.Vorbis;
            s.quality = quality;
            s.sampleRateSetting = AudioSampleRateSetting.PreserveSampleRate;
            s.preloadAudioData = true;
            imp.defaultSampleSettings = s;
            imp.forceToMono = true;
            imp.loadInBackground = false;
            imp.SaveAndReimport();
            builds.Add(new AssetBundleBuild { assetBundleName = Path.GetFileNameWithoutExtension(path).ToLower(), assetNames = new[] { path } });
        }
        BuildPipeline.BuildAssetBundles(outDir, builds.ToArray(), BuildAssetBundleOptions.UncompressedAssetBundle, EditorUserBuildSettings.activeBuildTarget);  // FSB5 é igual em qualquer plataforma
        Debug.Log("BuildAudio: " + builds.Count + " clipes em " + outDir);
    }
}
