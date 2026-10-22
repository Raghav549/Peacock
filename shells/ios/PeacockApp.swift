import SwiftUI

@main
struct PeacockShellApp: App {
    var body: some Scene { WindowGroup { ContentView() } }
}

struct ContentView: View {
    @State private var output = "सूत्रं चालयितुम् सज्जम्"
    @State private var running = false

    var body: some View {
        NavigationStack {
            ScrollView {
                Text(output)
                    .font(.system(.body, design: .monospaced))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .textSelection(.enabled)
                    .padding()
            }
            .navigationTitle("PEACOCK सूत्र")
            .toolbar { Button("पुनः चालय", action: execute).disabled(running) }
            .onAppear(perform: execute)
        }
    }

    private func execute() {
        guard !running else { return }
        running = true
        output = "चलति…"
        DispatchQueue.global(qos: .userInitiated).async {
            var nativeError: NSError?
            let data = PeacockRunner.run(withError: &nativeError)
            var text = String(decoding: data, as: UTF8.self)
            if let nativeError { text += "\n" + nativeError.localizedDescription }
            DispatchQueue.main.async {
                output = text
                running = false
            }
        }
    }
}
