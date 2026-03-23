/*
 * synapse_infer.cpp
 *
 * LibTorch C++ wrapper for the SYNAPSE SynapseBrain model.
 *
 * Loads a TorchScript model exported by SynapseBrain.save_torchscript()
 * and runs a single forward pass, printing the top predicted class index
 * and its probability.
 *
 * Build:
 *   See CMakeLists.txt — requires LibTorch (CPU build).
 *
 * Usage:
 *   ./synapse_infer [model_path] [token_id ...]
 *
 *   model_path   Path to synapse_model.pt (default: synapse_model.pt)
 *   token_id ... Space-separated integer token IDs that form the context
 *                window fed to the LSTM.  Must match the window length the
 *                model was traced with (default window = 4).
 *
 * Examples:
 *   ./synapse_infer                          # loads ./synapse_model.pt, zeros input
 *   ./synapse_infer synapse_model.pt 0 1 2 3 # explicit token IDs
 */

#include <torch/script.h>
#include <torch/torch.h>

#include <iostream>
#include <stdexcept>
#include <string>
#include <vector>

int main(int argc, char* argv[]) {
    // ------------------------------------------------------------------ //
    // 1. Parse arguments
    // ------------------------------------------------------------------ //
    std::string model_path = "synapse_model.pt";
    std::vector<int64_t> token_ids;

    if (argc >= 2) {
        model_path = argv[1];
    }
    for (int i = 2; i < argc; ++i) {
        token_ids.push_back(static_cast<int64_t>(std::stol(argv[i])));
    }

    // ------------------------------------------------------------------ //
    // 2. Load the TorchScript model
    // ------------------------------------------------------------------ //
    torch::jit::script::Module model;
    try {
        model = torch::jit::load(model_path, torch::kCPU);
    } catch (const c10::Error& e) {
        std::cerr << "[ERROR] Failed to load model from \"" << model_path
                  << "\"\n"
                  << "        " << e.what() << "\n"
                  << "        Make sure the file exists and was produced by "
                     "SynapseBrain.save_torchscript().\n";
        return 1;
    }
    model.eval();
    std::cout << "[OK] Loaded model from \"" << model_path << "\"\n";

    // ------------------------------------------------------------------ //
    // 3. Build input tensor  [1, window]  dtype=torch.long
    //    If the caller didn't supply token IDs we use a zero context,
    //    which is valid (padding_idx=0 in the Embedding layer).
    // ------------------------------------------------------------------ //

    // Determine window length: use supplied IDs or default to 4.
    const int64_t window =
        token_ids.empty() ? 4 : static_cast<int64_t>(token_ids.size());

    if (token_ids.empty()) {
        token_ids.assign(static_cast<size_t>(window), 0LL);
        std::cout << "[INFO] No token IDs supplied — using zero context "
                     "(window=" << window << ")\n";
    }

    torch::Tensor input = torch::tensor(token_ids, torch::kLong).unsqueeze(0);
    // input shape: [1, window]

    std::cout << "[INFO] Input tensor: " << input << "\n";

    // ------------------------------------------------------------------ //
    // 4. Run inference
    // ------------------------------------------------------------------ //
    std::vector<torch::jit::IValue> inputs;
    inputs.push_back(input);

    torch::Tensor logits;
    try {
        logits = model.forward(inputs).toTensor();  // [1, vocab_size]
    } catch (const c10::Error& e) {
        std::cerr << "[ERROR] Forward pass failed: " << e.what() << "\n"
                  << "        Check that the token IDs and window size match "
                     "the trained model.\n";
        return 1;
    }

    // ------------------------------------------------------------------ //
    // 5. Compute probabilities and report
    // ------------------------------------------------------------------ //
    torch::Tensor probs    = torch::softmax(logits, /*dim=*/1).squeeze(0);
    torch::Tensor top_prob = std::get<0>(probs.max(0));
    torch::Tensor top_idx  = std::get<1>(probs.max(0));

    const int64_t vocab_size = probs.size(0);
    const int64_t predicted  = top_idx.item<int64_t>();
    const float   confidence = top_prob.item<float>();

    std::cout << "\n";
    std::cout << "┌─────────────────────────────────┐\n";
    std::cout << "│  SYNAPSE Inference Result        │\n";
    std::cout << "├─────────────────────────────────┤\n";
    std::cout << "│  Vocab size  : " << vocab_size  << "\n";
    std::cout << "│  Predicted   : token[" << predicted << "]\n";
    std::cout << "│  Confidence  : "
              << static_cast<int>(confidence * 100.0f) << "%\n";
    std::cout << "└─────────────────────────────────┘\n";

    // Full probability distribution
    std::cout << "\nFull distribution:\n";
    for (int64_t i = 0; i < vocab_size; ++i) {
        float p = probs[i].item<float>();
        std::cout << "  token[" << i << "] : " << p * 100.0f << "%\n";
    }

    return 0;
}
