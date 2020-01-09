"""Sequence-to-sequence model for human motion prediction."""
import random
import torch
from torch import nn


class Seq2SeqModel(nn.Module):
    """Sequence-to-sequence model for human motion prediction"""

    def __init__(self,
                 architecture,
                 rnn_size,
                 num_layers=1,
                 num_joints=21,
                 residual_velocities=False,
                 dropout=0.0,
                 teacher_ratio=0.0):
        """Create the model.
        Args:
          architecture: [basic, tied] whether to tie the encoder and decoder.
          rnn_size: number of units in the rnn.
          num_layers: number of rnns to stack.
          residual_velocities: whether to use a residual connection that models velocities.
        """
        super(Seq2SeqModel, self).__init__()

        self.input_size = num_joints*3
        self.num_joints = num_joints
        # Summary writers for train and test runs
        self.rnn_size = rnn_size
        self.dropout = nn.Dropout(dropout)
        self.teacher_forcing = teacher_ratio
        self.residual_velocities = residual_velocities
        # === Create the RNN that will keep the state ===
        self.encoder = torch.nn.GRU(
            self.input_size, self.rnn_size, batch_first=True, num_layers=num_layers)
        self.decoder = torch.nn.GRUCell(
            self.input_size, self.rnn_size)
        self.projector = nn.Linear(self.rnn_size, self.input_size)

    def forward(self, encoder_inputs, decoder_inputs):
        """
        Args:
            encoder_inputs: batch of dance pose sequences , shape=(batch_size,source_seq_length,num_joints*3)
            decoder_inputs: batch of dance pose sequences , shape=(batch_size,target_seq_length-1,num_joints*3)
        Returns:
            outputs: batch of predicted dance pose sequences, shape=(batch_size,target_seq_length-1,num_joints*3)
        """
        # First calculate the encoder hidden state
        encoder_inputs = encoder_inputs.view(-1, encoder_inputs.size(1), self.input_size)
        decoder_inputs = decoder_inputs.view(-1, decoder_inputs.size(1), self.input_size)
        all_hidden_states, encoder_hidden_state = self.encoder(encoder_inputs)

        outputs = []
        first_decode = True
        next_state = encoder_hidden_state[-1]
        # Iterate over decoder inputs
        for inp in decoder_inputs.transpose(0, 1):
            # Perform teacher forcing
            if random.random() < self.teacher_forcing and not first_decode:
                inp = prev_output
            next_state = self.decoder(inp, next_state)
            # Apply residual network to help in smooth transition between subsequent poses
            if self.residual_velocities:
                output = inp + self.projector(self.dropout(next_state))
            else:
                output = self.projector(self.dropout(next_state))
            # Store the output for Teacher Forcing: use the prediction as
            # the next input instead of feeding the ground truth
            prev_output = output
            outputs.append(output.view(-1, self.num_joints, 3))
            first_decode = False

        outputs = torch.stack(outputs)
        return outputs.transpose(0, 1)

    def generate(self, warmup_input, n_frames):
        with torch.no_grad():
            warmup_input = warmup_input.view(-1, warmup_input.size(1), self.input_size)
            outputs = []
            batch_size = warmup_input.size(0)
            hidden = torch.zeros(batch_size, self.rnn_size)
            for inp in warmup_input.transpose(0, 1):
                hidden = self.decoder(inp, hidden)

            last_warmup_input = warmup_input.transpose[-1]
            if self.residual_velocities:
                output = last_warmup + self.projector(hidden)
            else:
                output = self.projector(hidden)

            outputs.append(output.view(-1, self.num_joints, 3))

            for _ in range(n_frames-1):
                hidden = self.decoder(output, hidden)
                if self.residual_velocities:
                    output = output + self.projector(hidden)
                else:
                    output = self.projector(hidden)
                outputs.append(output.view(-1, self.num_joints, 3))
            
            outputs = torch.stack(outputs)
            return outputs.transpose(0, 1)
            

