#include <iostream>
#include <string>
#include <vector>
#include <unordered_map>
#include <algorithm>
#include <memory>
#include <sstream>
using namespace std;

struct Node {
    int weight;         
    int number;         
    string symbol; 

    Node* parent;
    Node* left;
    Node* right;

   
    Node(int w, int num, const string& sym = "", Node* p = nullptr, Node* l = nullptr, Node* r = nullptr)
        : weight(w), number(num), symbol(sym), parent(p), left(l), right(r) {}
};

class AdaptiveHuffman {
public:
    AdaptiveHuffman();
    ~AdaptiveHuffman();

    string encode(const vector<string>& symbols);
    string decode(const string& bitstream);

private:
    Node* root;
    Node* NYT_node;
    Node* NCW_node;

   
    unordered_map<string, Node*> symbol_to_node;

    vector<Node*> nodes_by_number;

    int next_node_number;

    void delete_tree(Node* node);
    string get_code_for_node(Node* node) const;
    Node* get_node_from_code(const string& code, size_t& pos) const;
    void swap_nodes(Node* node1, Node* node2);
    Node* find_leader_in_block(Node* node);
    void add_new_symbol(const string& symbol);
    void update_tree(Node* start_node);
};


AdaptiveHuffman::AdaptiveHuffman() : next_node_number(512) {

    root = new Node(0, next_node_number--);

    NYT_node = new Node(0, next_node_number--, "NYT");

    NCW_node = new Node(0, next_node_number--, "NCW");

    root->left = NYT_node;
    root->right = NCW_node;
    NYT_node->parent = root;
    NCW_node->parent = root;

    nodes_by_number.push_back(NCW_node);
    nodes_by_number.push_back(NYT_node);
    nodes_by_number.push_back(root);

    sort(nodes_by_number.begin(), nodes_by_number.end(), [](Node* a, Node* b) {
        return a->number > b->number;
    });
}

AdaptiveHuffman::~AdaptiveHuffman() {
    delete_tree(root);
}

void AdaptiveHuffman::delete_tree(Node* node) {
    if (node) {
        delete_tree(node->left);
        delete_tree(node->right);
        delete node;
    }
}

string AdaptiveHuffman::encode(const vector<string>& symbols) {
    string result = "";

    for (const auto& symbol : symbols) {
        if (symbol_to_node.count(symbol)) {
            Node* node = symbol_to_node[symbol];
            result += get_code_for_node(node);
            update_tree(node);
        } else {
            result += get_code_for_node(NCW_node);
            update_tree(NCW_node);

            result += symbol + "|";

            add_new_symbol(symbol);
            update_tree(symbol_to_node[symbol]);
        }
    }
    return result;
}

string AdaptiveHuffman::decode(const string& bitstream) {
    string result = "";
    size_t pos = 0;

    while (pos < bitstream.length()) {
        Node* node = get_node_from_code(bitstream, pos);

        if (!node) {
            cerr << "Error: Decoding failed. Invalid code at pos " << pos << endl;
            break;
        }

        string symbol = "";
        if (node == NCW_node) {
            update_tree(NCW_node);

            size_t end_pos = bitstream.find('|', pos);
            if (end_pos == string::npos) break;
            symbol = bitstream.substr(pos, end_pos - pos);
            pos = end_pos + 1;

            add_new_symbol(symbol);
        } else {
            symbol = node->symbol;
        }

        result += symbol + " ";
        update_tree(symbol_to_node[symbol]);
    }
    if (!result.empty()) {
        result.pop_back();
    }
    return result;
}

string AdaptiveHuffman::get_code_for_node(Node* node) const {
    if (node->parent == nullptr) return "";

    string code = "";
    Node* current = node;
    while (current->parent != nullptr) {
        if (current->parent->left == current) {
            code += '0';
        } else {
            code += '1';
        }
        current = current->parent;
    }
    reverse(code.begin(), code.end());
    return code;
}

Node* AdaptiveHuffman::get_node_from_code(const string& code, size_t& pos) const {
    Node* current = root;
    while (current && (current->left || current->right)) { 
        if (pos >= code.length()) return nullptr; 
        char bit = code[pos++];
        if (bit == '0') {
            current = current->left;
        } else if (bit == '1') {
            current = current->right;
        } else { 
            pos--; 
            return nullptr;
        }
    }
    return current;
}


void AdaptiveHuffman::add_new_symbol(const string& symbol) {
    Node* old_nyt = NYT_node;

    old_nyt->symbol = "";

    Node* new_symbol_node = new Node(0, old_nyt->number - 1, symbol, old_nyt);

    NYT_node = new Node(0, old_nyt->number - 2, "NYT", old_nyt);

    old_nyt->left = NYT_node;
    old_nyt->right = new_symbol_node;
    old_nyt->number = next_node_number--;

    symbol_to_node[symbol] = new_symbol_node;

    nodes_by_number.push_back(new_symbol_node);
    nodes_by_number.push_back(NYT_node);

    sort(nodes_by_number.begin(), nodes_by_number.end(), [](Node* a, Node* b) {
        return a->number > b->number;
    });
}

Node* AdaptiveHuffman::find_leader_in_block(Node* node) {
    Node* leader = node;
    for (const auto& other_node : nodes_by_number) {
        if (other_node->weight == node->weight && other_node->number > leader->number) {
            leader = other_node;
        }
    }
    return leader;
}


void AdaptiveHuffman::swap_nodes(Node* node1, Node* node2) {
    if (node1 == node2 || !node1->parent || !node2->parent || node1->parent == node2 || node2->parent == node1) {
        return; 
    }

    auto it1 = find(nodes_by_number.begin(), nodes_by_number.end(), node1);
    auto it2 = find(nodes_by_number.begin(), nodes_by_number.end(), node2);
    if(it1 != nodes_by_number.end() && it2 != nodes_by_number.end()){
        iter_swap(it1, it2);
    }

    swap(node1->number, node2->number);

    Node* p1 = node1->parent;
    Node* p2 = node2->parent;
    bool is_node1_left = (p1->left == node1);
    bool is_node2_left = (p2->left == node2);

    if (is_node1_left) p1->left = node2;
    else p1->right = node2;

    if (is_node2_left) p2->left = node1;
    else p2->right = node1;

    swap(node1->parent, node2->parent);
}

void AdaptiveHuffman::update_tree(Node* start_node) {
    Node* current = start_node;

    while (current != nullptr) {

        Node* leader = find_leader_in_block(current);

        if (leader != current) {
            swap_nodes(current, leader);
        }

        current->weight++;

        current = current->parent;
    }
}

vector<string> tokenize(const string& text) {
    vector<string> tokens;
    string current_token;
    for (char c : text) {
        if (isspace(c)) {
            if (!current_token.empty()) {
                tokens.push_back(current_token);
                current_token.clear();
            }
            if (!isspace(c)) {
                tokens.push_back(string(1, c));
            }
        } else {
            current_token += c;
        }
    }
    if (!current_token.empty()) {
        tokens.push_back(current_token);
    }
    return tokens;
}

int main() {
    AdaptiveHuffman coder;

    string text = "I am a gay living in a gay world because the world is gay.";
    cout << "Original Text:\n" << text << endl;

    vector<string> words = tokenize(text);
    cout << "\nTokens to be encoded:" << endl;
    for(const auto& w : words) cout << "'" << w << "' ";
    cout << endl;

    string compressed_data = coder.encode(words);
    cout << "\nEncoded Bitstream (with raw symbols for new words):\n" << compressed_data << endl;

    AdaptiveHuffman decoder;
    string decompressed_text = decoder.decode(compressed_data);
    cout << "\nDecompressed Text:\n" << decompressed_text << endl;

    cout << "\nVerification:" << endl;
    stringstream ss;
    for(size_t i = 0; i < words.size(); ++i) {
        ss << words[i];
        if (i < words.size() - 1 && words[i+1].length() >= 1) {
            ss << " ";
        }
    }
    string reconstructed_original = ss.str();

    if (decompressed_text == reconstructed_original) {
        cout << "Success! Decompressed text matches the original." << endl;
    } else {
        cout << "Failure! Decompressed text does not match." << endl;
        cout << "Original (reconstructed): " << reconstructed_original << endl;
    }

    return 0;
}