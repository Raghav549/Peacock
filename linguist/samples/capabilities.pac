// Capabilities must be declared by the calling function and granted by the host.
module capability_sample

use fs
use process

fn main() -> Unit {
    capability fs;
    let path = process.args().get(0);
    let text = fs.read_text(path);
    print("characters: " + str(len(text)));
}
